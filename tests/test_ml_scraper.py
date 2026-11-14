"""Scraping do Mercado Livre: navegador autenticado, URLs de produto e fila.

Contexto real (13/11/2026): o ML passou a responder `/ofertas` com uma tela de
verificação de conta. Sem sessão, HTTP 200 vindo de `/gz/account-verification`
com zero cards; com cookie, `/captcha/wall/web-risk-verification`. Em 48h, 54
de 57 ciclos de coleta trouxeram 0 ofertas. No Chromium com o perfil do Link
Builder a mesma página devolveu 54 cards — é o caminho que este módulo cobre.

A outra ponta: URLs de perfil/lista/tracking chegavam ao `createLink`, que
responde "URL Invalid" (error_code 100). A cascata tratava isso como sessão
expirada e guardava a URL em `ofertas_pendentes_ml`, onde ela nunca funcionaria.
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))

import isolamento  # noqa: E402,F401  (redireciona db/grok/cadência)
import ofertas.db as db  # noqa: E402
from ofertas.models import Oferta  # noqa: E402
from ofertas.sources import mercadolivre, ml_auth  # noqa: E402

HTML_CARD = """
<html><body>
<div class="poly-card">
  <a class="poly-component__title"
     href="https://www.mercadolivre.com.br/creatina-500g/p/MLB1234567">
     Creatina Monohidratada 500g
  </a>
  <div class="poly-price__current">
    <span class="andes-money-amount__fraction">59</span>
    <span class="andes-money-amount__cents">90</span>
  </div>
  <img class="poly-component__picture" src="https://http2.mlstatic.com/creatina.jpg">
</div>
</body></html>
"""


class TestUrlDeProduto(unittest.TestCase):
    def test_aceita_anuncios(self):
        for url in (
            "https://www.mercadolivre.com.br/o-boticario-quasar-blue-desodorante",
            "https://www.mercadolivre.com.br/p/MLB12345678",
            "https://produto.mercadolivre.com.br/MLB-5318134527-tenis-mizuno",
            "https://meli.la/1HQxKnG",
            # slug de produto que comeca com "ofertas" nao pode ser confundido
            "https://www.mercadolivre.com.br/ofertas-do-dia-boticario",
        ):
            self.assertTrue(mercadolivre.e_url_de_produto(url), url)

    def test_recusa_paginas_que_nao_sao_anuncio(self):
        for url in (
            "https://www.mercadolivre.com.br/social/felipericardo",
            "https://www.mercadolivre.com.br/social/nerdofertas/lists/8d51d4ca",
            "https://mercadolivre.com/sec/2diQaHy",
            "https://www.mercadolivre.com.br/scfeed/",
            "https://www.mercadolivre.com.br/gz/account-verification?go=x",
            "https://www.mercadolivre.com.br/ofertas",
            "https://www.mercadolivre.com.br/afiliados/linkbuilder",
            "https://click1.mercadolivre.com.br/mclics/clicks/external/MLB/count",
        ):
            self.assertFalse(mercadolivre.e_url_de_produto(url), url)

    def test_recusa_vazio_e_outro_dominio(self):
        self.assertFalse(mercadolivre.e_url_de_produto(None))
        self.assertFalse(mercadolivre.e_url_de_produto(""))
        self.assertFalse(mercadolivre.e_url_de_produto("https://example.com/produto"))


class TestConverterRecusaNaoProduto(unittest.TestCase):
    def test_nao_gera_link_para_perfil(self):
        with patch.object(mercadolivre, "gerar_links_afiliado") as gerar:
            with self.assertRaises(RuntimeError) as ctx:
                mercadolivre.converter(
                    "https://www.mercadolivre.com.br/social/felipericardo")
        self.assertIn("não é de produto", str(ctx.exception))
        gerar.assert_not_called()

    def test_meli_la_que_expande_para_perfil_e_recusado(self):
        resposta = MagicMock()
        resposta.url = "https://www.mercadolivre.com.br/social/felipericardo"
        with patch.object(mercadolivre, "sessao", return_value=MagicMock(
                get=MagicMock(return_value=resposta))), \
             patch.object(mercadolivre, "gerar_links_afiliado") as gerar:
            with self.assertRaises(RuntimeError):
                mercadolivre.converter("https://meli.la/1HQxKnG")
        gerar.assert_not_called()


class _PaginaFalsa:
    def __init__(self, html=HTML_CARD, url="https://www.mercadolivre.com.br/ofertas",
                 url_final=None):
        self._html = html
        self.url = url
        self._url_final = url_final
        self.goto = MagicMock(side_effect=self._goto)

    def _goto(self, url, **_):
        # no ML real, o goto pode terminar em outra URL (verificação de conta)
        self.url = self._url_final or url

    def wait_for_selector(self, *_a, **_k):
        if "poly-card" not in self._html:
            raise TimeoutError("sem cards")

    def content(self):
        return self._html


class _CtxFalso:
    def __init__(self, pagina):
        self.pages = [pagina]
        self.fechado = False

    def close(self):
        self.fechado = True


class TestColetaNoNavegador(unittest.TestCase):
    def test_parseia_pagina_do_navegador(self):
        ctx = _CtxFalso(_PaginaFalsa())
        with patch.object(mercadolivre, "_abrir_contexto", return_value=ctx):
            ofertas = mercadolivre._coletar_no_navegador(
                MagicMock(), [("https://www.mercadolivre.com.br/ofertas", "todas")])

        self.assertEqual(len(ofertas), 1)
        self.assertEqual(ofertas[0].titulo, "Creatina Monohidratada 500g")
        self.assertAlmostEqual(ofertas[0].preco, 59.9)
        self.assertTrue(ctx.fechado)

    def test_pagina_de_verificacao_levanta_erro(self):
        pagina = _PaginaFalsa(
            html="<html><body>Olá! Para continuar, acesse sua conta</body></html>",
            url_final="https://www.mercadolivre.com.br/gz/account-verification?go=x")
        ctx = _CtxFalso(pagina)
        with patch.object(mercadolivre, "_abrir_contexto", return_value=ctx):
            with self.assertRaises(RuntimeError) as e:
                mercadolivre._coletar_no_navegador(MagicMock(), [("x", "todas")])
        self.assertIn("verificação de conta", str(e.exception))
        self.assertTrue(ctx.fechado)


class TestBuscarOfertas(unittest.TestCase):
    def setUp(self):
        self._fonte = mercadolivre.config.fonte_ml
        mercadolivre.config.fonte_ml = {
            "ativa": True, "paginas": 1, "categorias": {"MLB1648": "Informática"}}
        mercadolivre._CURSOR_ROTACAO = 0
        mercadolivre._BLOQUEIO_ATE = 0.0

    def tearDown(self):
        mercadolivre.config.fonte_ml = self._fonte
        mercadolivre._CURSOR_ROTACAO = 0
        mercadolivre._BLOQUEIO_ATE = 0.0

    def test_usa_navegador_quando_ha_sessao(self):
        oferta = Oferta(plataforma="mercadolivre", id_produto="MLB1",
                        url_produto="https://www.mercadolivre.com.br/x/p/MLB1",
                        titulo="x")
        with patch.object(mercadolivre, "tem_sessao", return_value=True), \
             patch.object(mercadolivre, "_buscar_via_navegador",
                          return_value=[oferta]) as navegador, \
             patch.object(mercadolivre, "_buscar_via_http") as http:
            resultado = mercadolivre.buscar_ofertas()
        self.assertEqual(resultado, [oferta])
        navegador.assert_called_once()
        http.assert_not_called()

    def test_cai_para_http_quando_navegador_falha(self):
        oferta = Oferta(plataforma="mercadolivre", id_produto="MLB2",
                        url_produto="https://www.mercadolivre.com.br/x/p/MLB2",
                        titulo="x")
        with patch.object(mercadolivre, "tem_sessao", return_value=True), \
             patch.object(mercadolivre, "_buscar_via_navegador",
                          side_effect=RuntimeError("perfil ocupado")), \
             patch.object(mercadolivre, "_buscar_via_http",
                          return_value=[oferta]) as http:
            resultado = mercadolivre.buscar_ofertas()
        self.assertEqual(resultado, [oferta])
        http.assert_called_once()

    def test_cai_para_http_quando_navegador_devolve_vazio(self):
        with patch.object(mercadolivre, "tem_sessao", return_value=True), \
             patch.object(mercadolivre, "_buscar_via_navegador", return_value=[]), \
             patch.object(mercadolivre, "_buscar_via_http", return_value=[]) as http:
            mercadolivre.buscar_ofertas()
        http.assert_called_once()

    def test_sem_sessao_usa_http_direto(self):
        with patch.object(mercadolivre, "tem_sessao", return_value=False), \
             patch.object(mercadolivre, "_buscar_via_navegador") as navegador, \
             patch.object(mercadolivre, "_buscar_via_http", return_value=[]):
            mercadolivre.buscar_ofertas()
        navegador.assert_not_called()


class TestRotacaoDePaginas(unittest.TestCase):
    """Não varrer 24 páginas por ciclo: /ofertas respondeu com captcha."""

    def setUp(self):
        self._fonte = mercadolivre.config.fonte_ml
        mercadolivre._CURSOR_ROTACAO = 0

    def tearDown(self):
        mercadolivre.config.fonte_ml = self._fonte
        mercadolivre._CURSOR_ROTACAO = 0

    def _config(self, categorias, paginas, por_ciclo):
        mercadolivre.config.fonte_ml = {
            "ativa": True, "paginas": paginas, "categorias": categorias,
            "paginas_por_ciclo": por_ciclo}

    def test_janela_respeita_limite_e_avanca(self):
        self._config({"MLB1": "a", "MLB2": "b", "MLB3": "c"}, 2, 2)
        primeira = mercadolivre._alvos_do_ciclo()
        segunda = mercadolivre._alvos_do_ciclo()
        terceira = mercadolivre._alvos_do_ciclo()

        self.assertEqual(len(primeira), 2)
        self.assertEqual(len(segunda), 2)
        self.assertNotEqual(primeira, segunda)
        # 6 páginas no total: três janelas de 2 cobrem tudo, sem repetir
        todas = primeira + segunda + terceira
        self.assertEqual(len({u for u, _ in todas}), 6)

    def test_janela_da_a_volta(self):
        self._config({"MLB1": "a"}, 3, 2)
        self.assertEqual(len(mercadolivre._alvos_do_ciclo()), 2)
        self.assertEqual(len(mercadolivre._alvos_do_ciclo()), 2)  # 2 + 1 (volta)
        self.assertEqual(mercadolivre._CURSOR_ROTACAO, 1)

    def test_limite_maior_que_o_total_devolve_tudo(self):
        self._config({"MLB1": "a"}, 1, 99)
        self.assertEqual(len(mercadolivre._alvos_do_ciclo()), 1)

    def test_valor_invalido_cai_no_padrao(self):
        self._config({"MLB1": "a"}, 1, "abc")
        self.assertEqual(len(mercadolivre._alvos_do_ciclo()), 1)
        mercadolivre.config.fonte_ml = {"ativa": True, "paginas": 1,
                                        "categorias": {"MLB1": "a"},
                                        "paginas_por_ciclo": 0}
        self.assertEqual(mercadolivre._paginas_por_ciclo(),
                         mercadolivre.PAGINAS_POR_CICLO_PADRAO)


class TestCaptchaUsaPlanoB(unittest.TestCase):
    """Captcha em /ofertas -> /mais-vendidos, sem insistir e sem HTTP inútil."""

    def setUp(self):
        self._fonte = mercadolivre.config.fonte_ml
        mercadolivre.config.fonte_ml = {
            "ativa": True, "paginas": 1, "categorias": {"MLB1": "a"}}
        mercadolivre._CURSOR_ROTACAO = 0
        mercadolivre._BLOQUEIO_ATE = 0.0
        self.oferta = Oferta(plataforma="mercadolivre", id_produto="MLB1",
                             url_produto="https://www.mercadolivre.com.br/x/p/MLB1",
                             titulo="x")

    def tearDown(self):
        mercadolivre.config.fonte_ml = self._fonte
        mercadolivre._CURSOR_ROTACAO = 0
        mercadolivre._BLOQUEIO_ATE = 0.0

    def test_captcha_sem_ofertas_vai_para_mais_vendidos(self):
        with patch.object(mercadolivre, "tem_sessao", return_value=True), \
             patch.object(mercadolivre, "_buscar_via_navegador",
                          side_effect=[mercadolivre._VerificacaoML("captcha", []),
                                       [self.oferta]]) as navegador, \
             patch.object(mercadolivre, "_buscar_via_http") as http:
            resultado = mercadolivre.buscar_ofertas()

        self.assertEqual(resultado, [self.oferta])
        self.assertEqual(navegador.call_count, 2)
        self.assertEqual(navegador.call_args_list[1][0][0],
                         mercadolivre._alvos_alternativos())
        http.assert_not_called()

    def test_ofertas_ja_coletadas_nao_sao_perdidas(self):
        anterior = Oferta(plataforma="mercadolivre", id_produto="MLB9",
                          url_produto="https://www.mercadolivre.com.br/y/p/MLB9",
                          titulo="y")
        with patch.object(mercadolivre, "tem_sessao", return_value=True), \
             patch.object(mercadolivre, "_buscar_via_navegador",
                          side_effect=mercadolivre._VerificacaoML(
                              "captcha", [anterior])) as navegador, \
             patch.object(mercadolivre, "_buscar_via_http") as http:
            resultado = mercadolivre.buscar_ofertas()

        self.assertEqual(resultado, [anterior])
        navegador.assert_called_once()
        http.assert_not_called()

    def test_ciclo_seguinte_nao_bate_no_captcha_de_novo(self):
        with patch.object(mercadolivre, "tem_sessao", return_value=True), \
             patch.object(mercadolivre, "_buscar_via_navegador",
                          side_effect=mercadolivre._VerificacaoML("captcha", [])) as navegador, \
             patch.object(mercadolivre, "_buscar_via_http") as http:
            mercadolivre.buscar_ofertas()
        self.assertTrue(mercadolivre._bloqueado())

        with patch.object(mercadolivre, "tem_sessao", return_value=True), \
             patch.object(mercadolivre, "_buscar_via_navegador",
                          return_value=[self.oferta]) as navegador2, \
             patch.object(mercadolivre, "_buscar_via_http") as http2:
            resultado = mercadolivre.buscar_ofertas()

        self.assertEqual(resultado, [self.oferta])
        # já vai direto na alternativa, sem tentar /ofertas outra vez
        self.assertEqual(navegador2.call_args_list[0][0][0],
                         mercadolivre._alvos_alternativos())
        http2.assert_not_called()

    def test_alternativa_falhando_devolve_vazio(self):
        with patch.object(mercadolivre, "tem_sessao", return_value=True), \
             patch.object(mercadolivre, "_buscar_via_navegador",
                          side_effect=[mercadolivre._VerificacaoML("captcha", []),
                                       RuntimeError("sem rede")]), \
             patch.object(mercadolivre, "_buscar_via_http") as http:
            resultado = mercadolivre.buscar_ofertas()

        self.assertEqual(resultado, [])
        http.assert_not_called()


class TestCascataIgnoraUrlInvalida(unittest.TestCase):
    def setUp(self):
        with db._conn() as c:
            c.execute("DELETE FROM ofertas_pendentes_ml")

    def test_nao_tenta_autenticacao_para_perfil(self):
        oferta = Oferta(
            plataforma="mercadolivre", id_produto="felipericardo",
            url_produto="https://www.mercadolivre.com.br/social/felipericardo",
            titulo="perfil")

        with patch.object(ml_auth, "obter_cookie_configurado", return_value="cookie_valido"), \
             patch.object(ml_auth, "_gerar_via_cookie_raw") as cookie:
            ml_auth.ml_auth_service.gerar_links_afiliado([oferta])

        cookie.assert_not_called()
        self.assertEqual(oferta.url_afiliado, "")
        self.assertEqual(db.total_ofertas_pendentes_ml(), 0)

    def test_pendencia_de_url_invalida_e_removida_ao_reprocessar(self):
        oferta = Oferta(
            plataforma="mercadolivre", id_produto="nerdofertas",
            url_produto="https://www.mercadolivre.com.br/social/nerdofertas",
            titulo="lista")
        db.salvar_oferta_pendente_ml(oferta, status="aguardando_autenticacao")
        self.assertEqual(db.total_ofertas_pendentes_ml(), 1)

        with patch.object(ml_auth, "obter_cookie_configurado", return_value="cookie_valido"), \
             patch.object(ml_auth, "_gerar_via_cookie_raw") as cookie:
            publicadas = asyncio.run(
                ml_auth.ml_auth_service.processar_ofertas_pendentes_async(bot=None))

        self.assertEqual(publicadas, 0)
        cookie.assert_not_called()
        self.assertEqual(db.total_ofertas_pendentes_ml(), 0)

    def test_pendencia_de_produto_continua_na_fila(self):
        """A limpeza não pode jogar fora pendência legítima."""
        oferta = Oferta(
            plataforma="mercadolivre", id_produto="MLB999",
            url_produto="https://www.mercadolivre.com.br/produto/p/MLB999",
            titulo="produto")
        db.salvar_oferta_pendente_ml(oferta, status="aguardando_autenticacao")

        with patch.object(ml_auth, "obter_cookie_configurado", return_value="cookie_valido"), \
             patch.object(ml_auth, "_gerar_via_cookie_raw",
                          side_effect=RuntimeError("sem rede")), \
             patch.object(mercadolivre, "reler_preco", return_value=(10.0, None)):
            asyncio.run(ml_auth.ml_auth_service.processar_ofertas_pendentes_async(bot=None))

        self.assertEqual(db.total_ofertas_pendentes_ml(), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
