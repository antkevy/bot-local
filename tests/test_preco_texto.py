"""Preco escrito no texto da mensagem, e o link curto da Amazon.

Duas correcoes que vieram da mesma medicao: dos 24 links de marketplace que o
NERD OFERTAS publica, nenhum devolvia preco, porque

  1. `s.shopee.com.br/3qNRstVRaQ` aponta para produto fora do catalogo de ofertas
     da Open API. A API responde lista vazia, o `converter` cai no fallback e
     monta Oferta(titulo="Oferta Shopee", preco=None) -- que passava por todos
     os filtros e era publicada como post vazio. O preco esta escrito na
     mensagem ("R$ 1.358") e e a unica fonte que sobra.

  2. `https://link.amazon/B09NnFj0N` nao era reconhecido por nenhuma plataforma,
     porque o `e_link` da Amazon aceitava so "amazon.com.br". Logo essas ofertas
     nem entravam no pipeline.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Esta suíte chega em registrar_publicacao() pelo pipeline e, sem isto, grava
# no data/cadencia.json de verdade. Já aconteceu: 41 registros para 2 posts.
import isolamento  # noqa: F401,E402

from ofertas.models import Oferta
from ofertas.sources import amazon
from ofertas.sources.telegram_scraper import pre_processar_mensagem
from ofertas.utils import extrair_precos_texto, parse_preco_br

# Mensagem real do NERD OFERTAS (id 140371), sem acentos para o arquivo ficar
# legivel no diff; o preco e a estrutura sao exatamente os do canal.
MSG_NERD = """\u27a1\ufe0f Lava Loucas Brastemp 8 Servicos

\u2705 R$ 1.358 \U0001f631\U0001f631

\U0001f3f7 Resgate todos os cupons desta pagina:
https://s.shopee.com.br/3qNRstVRaQ

\U0001f6d2 https://s.shopee.com.br/4LJXIcT2Yq
"""


class TestExtrairPrecosTexto(unittest.TestCase):
    """O parser central. `parse_preco_br` faz a conversao; isto escolhe o valor."""

    def test_formatos_que_os_canais_escrevem(self):
        for texto, esperado in (
            ("R$ 1.358", 1358.0),
            ("R$ 1.358,90", 1358.90),
            ("R$ 1358", 1358.0),
            ("R$1358,90", 1358.90),
            ("R$ 89", 89.0),
            ("R$ 1.234", 1234.0),
        ):
            with self.subTest(texto=texto):
                self.assertEqual(extrair_precos_texto(texto)[0], esperado)

    def test_o_que_o_parse_ja_fazia_continua_valendo(self):
        """O novo helper nao pode ter quebrado quem ja chamava o parser antigo."""
        for texto, esperado in (("R$ 1.358", 1358.0), ("R$ 1.358,90", 1358.90),
                                ("R$ 3.99", 3.99), ("R$ 1.234", 1234.0)):
            with self.subTest(texto=texto):
                self.assertEqual(parse_preco_br(texto), esperado)

    def test_de_por(self):
        self.assertEqual(extrair_precos_texto("De R$ 1.999\nPor R$ 1.358"),
                         (1358.0, 1999.0))
        self.assertEqual(extrair_precos_texto("De R$ 1.999\nPor apenas R$ 1.358"),
                         (1358.0, 1999.0))

    def test_mensagem_real_do_nerd_ofertas(self):
        self.assertEqual(extrair_precos_texto(MSG_NERD)[0], 1358.0)

    def test_nao_aceita_numero_aleatorio_como_preco(self):
        """32 polegadas, 4.7 estrelas e 2 pedidos nao viram R$."""
        texto = "Frete gratis em 2 pedidos, tela de 32 polegadas, nota 4.7, 5 stars"
        self.assertEqual(extrair_precos_texto(texto), (None, None))

    def test_nao_calcula_desconto_sem_dados_suficientes(self):
        """Um preco solto nao vira preco antigo: sem os dois numeros, sem desconto."""
        preco, antigo = extrair_precos_texto("Produto incrivel por R$ 89")
        self.assertEqual(preco, 89.0)
        self.assertIsNone(antigo)
        # E a property do model, que e quem decide o desconto na legenda.
        oferta = Oferta(plataforma="shopee", id_produto="1", titulo="X",
                        preco=preco, preco_original=antigo)
        self.assertIsNone(oferta.desconto)

    def test_de_no_meio_do_texto_e_limite_de_cupom_nao_preco_antigo(self):
        """"acima de R$ 49" e limite, nao "de R$ 1.999". Tratar como preco antigo
        fabricaria um desconto que ninguem escreveu."""
        for texto in ("10% OFF acima de R$ 49", "a partir de R$ 10",
                      "somente a partir de R$ 10", "limite de R$ 50 OFF",
                      "até R$ 99", "menor que R$ 5"):
            with self.subTest(texto=texto):
                self.assertEqual(extrair_precos_texto(texto), (None, None),
                                 "limite de cupom virou preco de oferta")

    def test_dois_precos_sem_marcacao_nao_acha_qual_e_o_preco(self):
        """Escolher o primeiro seria inventar preco."""
        self.assertEqual(extrair_precos_texto("Cupom de R$ 20 no carrinho de R$ 999"),
                         (None, None))

    def test_ausencia_de_preco(self):
        for texto in ("", None, "sem preco nenhum aqui", "🔥 liquidaçao imperdivel 🔥"):
            with self.subTest(texto=texto):
                self.assertEqual(extrair_precos_texto(texto), (None, None))

    def test_apenas_preco_antigo_sem_marcador_de_atual(self):
        self.assertEqual(extrair_precos_texto("De R$ 250"), (250.0, None))

    def test_preco_igual_antigo_e_atual_nao_inventa_desconto(self):
        self.assertEqual(extrair_precos_texto("De R$ 100\nPor R$ 100"), (100.0, None))


class TestPreProcessarMensagem(unittest.TestCase):
    """`pre_processar_mensagem` e o lugar unico onde o preco do texto entra."""

    def test_expoe_o_preco_do_texto(self):
        pre = pre_processar_mensagem(MSG_NERD)
        self.assertEqual(pre["preco_texto"], 1358.0)
        self.assertIsNone(pre["preco_antigo_texto"])

    def test_expoe_o_preco_antigo_quando_o_marcador_existe(self):
        pre = pre_processar_mensagem("De R$ 1.999\nPor R$ 1.358\nhttps://s.shopee.com.br/x")
        self.assertEqual(pre["preco_texto"], 1358.0)
        self.assertEqual(pre["preco_antigo_texto"], 1999.0)

    def test_ausencia_de_preco_vira_none_e_nao_erro(self):
        pre = pre_processar_mensagem("Promocao imperdivel no link https://s.shopee.com.br/x")
        self.assertIsNone(pre["preco_texto"])
        self.assertIsNone(pre["preco_antigo_texto"])

    def test_as_outras_chaves_continuam_igual(self):
        pre = pre_processar_mensagem(MSG_NERD)
        self.assertIn("https://s.shopee.com.br/3qNRstVRaQ", pre["urls"])
        self.assertTrue(pre["links_marketplace"])
        self.assertTrue(pre["tem_links_afiliados_potenciais"])
        self.assertEqual(pre["texto_original"], MSG_NERD.strip())


class TestAmazonLinkCurto(unittest.TestCase):
    """`https://link.amazon/B09NnFj0N` e o formato que o canal publica."""

    def test_reconhece_o_formato_do_canal(self):
        self.assertTrue(amazon.e_link("https://link.amazon/B09NnFj0N"))

    def test_reconhece_sem_protocolo(self):
        """O `e_link` e classificador, nao extrator: se ele reconhece a forma
        sem protocolo, o `link.amazon/...` colado no texto tambem passa."""
        self.assertTrue(amazon.e_link("link.amazon/B09NnFj0N"))

    def test_urls_reais_continuam_reconhecidas(self):
        for url in ("https://www.amazon.com.br/dp/B09NnFj0N",
                    "https://amazon.com.br/gp/product/B09SGPQ2J7",
                    "https://amzn.to/3xY2abc",
                    "https://www.amazon.com/dp/B08N5WRWNW"):
            with self.subTest(url=url):
                self.assertTrue(amazon.e_link(url))

    def test_dominio_falso_que_contem_amazon(self):
        """Antes a checagem era por substring, e estes tres passavam como Amazon --
        o pipeline pagava com a tag do usuario e publicava."""
        for url in ("https://notamazon.com.br/x",
                    "https://amazon.com.br.evil.tld/x",
                    "https://meu.link.amazon.falso.tld/x"):
            with self.subTest(url=url):
                self.assertFalse(amazon.e_link(url))

    def test_nao_e_amazon(self):
        for url in ("https://s.shopee.com.br/3qNRstVRaQ", "", None):
            with self.subTest(url=url):
                self.assertFalse(amazon.e_link(url))

    def test_o_token_curto_nao_e_o_asin(self):
        """O caminho do link curto tem 9 digitos e e rastreamento; o ASIN tem 10 e
        so existe na URL de destino. Sem expandir, `converter` morria em
        "Nao encontrei o ASIN"."""
        import re
        re_asin = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})")
        self.assertIsNone(re_asin.search("https://link.amazon/B09NnFj0N"))
        self.assertIsNotNone(re_asin.search("https://www.amazon.com.br/dp/B09SGPQ2J7"))


class TestPreferirPrecoDaPlataforma(unittest.TestCase):
    """Preco de API/pagina manda no texto. O texto so preenche o buraco."""

    def setUp(self):
        from ofertas import pipeline
        self._pipeline = pipeline

    def _aplica(self, oferta: Oferta, preco_txt, antigo_txt) -> Oferta:
        self._pipeline._aplicar_preco_texto(
            oferta, {"preco_texto": preco_txt, "preco_antigo_texto": antigo_txt})
        return oferta

    def test_texto_so_entra_quando_a_plataforma_nao_trouxe_preco(self):
        """O caso real: a Open API responde vazio para produto fora do catalogo."""
        oferta = Oferta(plataforma="shopee", id_produto="58255664210",
                        titulo="Oferta Shopee", preco=None)
        self._aplica(oferta, 1358.0, None)
        self.assertEqual(oferta.preco, 1358.0)

    def test_preco_da_plataforma_nao_e_sobrescrito(self):
        """A Amazon leu 89.90 na pagina enquanto a mensagem dizia R$ 89. Quem
        consultou a fonte manda: o preco da pagina e o do momento da compra."""
        oferta = Oferta(plataforma="amazon", id_produto="B09SGPQ2J7",
                        titulo="Licor Ballena", preco=89.90, preco_original=129.99)
        self._aplica(oferta, 89.0, None)
        self.assertEqual(oferta.preco, 89.90)
        self.assertEqual(oferta.preco_original, 129.99)

    def test_preco_invalido_da_plataforma_e_substituido(self):
        """0, negativo e NaN nao sao preco: sao o placeholder que a pagina
        bloqueada devolve, e o texto e melhor que placeholder."""
        for ruim in (None, 0.0, -10.0, float("nan"), float("inf")):
            with self.subTest(preco=ruim):
                oferta = Oferta(plataforma="shopee", id_produto="1",
                                titulo="X", preco=ruim)
                self._aplica(oferta, 1358.0, None)
                self.assertEqual(oferta.preco, 1358.0)

    def test_desconto_so_com_os_dois_numeros(self):
        oferta = Oferta(plataforma="shopee", id_produto="1", titulo="X")
        self._aplica(oferta, 1358.0, 1999.0)
        self.assertEqual(oferta.preco, 1358.0)
        self.assertEqual(oferta.preco_original, 1999.0)
        self.assertEqual(oferta.desconto, 32)

    def test_sem_preco_antigo_no_texto_nao_inventa_original(self):
        oferta = Oferta(plataforma="shopee", id_produto="1", titulo="X")
        self._aplica(oferta, 1358.0, None)
        self.assertIsNone(oferta.preco_original)
        self.assertIsNone(oferta.desconto)

    def test_original_abaixo_do_atual_e_descartado(self):
        """"de R$ 10 por R$ 89" nao e desconto; e o preco antigo menor que o
        atual, que nao existe em desconto nenhum."""
        oferta = Oferta(plataforma="shopee", id_produto="1", titulo="X")
        self._aplica(oferta, 89.0, 10.0)
        self.assertIsNone(oferta.preco_original)
        self.assertIsNone(oferta.desconto)

    def test_texto_sem_preco_nao_toca_na_oferta(self):
        oferta = Oferta(plataforma="shopee", id_produto="1", titulo="X", preco=None)
        self._aplica(oferta, None, None)
        self.assertIsNone(oferta.preco)

    def test_preco_herdado_do_texto_passa_no_filtro(self):
        """Fecha o ciclo: era exatamente este o buraco que deixava o post vazio
        passar. Com o preco vindo do texto, a oferta passa a ter preco real."""
        from ofertas.filters import passes_product_filters
        oferta = Oferta(plataforma="shopee", id_produto="58255664210",
                        titulo="Lava Loucas Brastemp 8 Servicos", preco=None)
        self.assertEqual(passes_product_filters(oferta)[1], "sem_preco")
        self._aplica(oferta, 1358.0, None)
        self.assertTrue(passes_product_filters(oferta)[0], passes_product_filters(oferta))


class TestPrecoNoPipeline(unittest.TestCase):
    """O preco do texto tem que chegar na oferta pelo caminho de producao.

    Testar `_aplicar_preco_texto` direto nao prova nada: a funcao pode estar
    perfeita e o pipeline simplesmente nao a chamar, e ai o preco continua
    None. Estes testes passam pela `processar_mensagem_telegram` inteira, que e
    o caminho que a mensagem do canal percorre.
    """

    def setUp(self):
        from ofertas import db
        self.banco_anterior = db.DB_PATH
        pasta = tempfile.mkdtemp(prefix="teste_preco_texto_")
        db.DB_PATH = Path(pasta) / "ofertas.db"
        db.init_db()

    def tearDown(self):
        from ofertas import db
        db.DB_PATH = self.banco_anterior

    def _roda(self, oferta_mock, texto=MSG_NERD, message_id=90210) -> dict:
        """Mensagem real -> pipeline real, so o conversor e a IA sao simulados."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch
        from ofertas import pipeline
        from ofertas.grok import GrokResult

        grok = GrokResult(tipo="produto",
                         titulo_otimizado="Lava Loucas Brastemp 8 Servicos",
                         tem_cupom=False, cupom=None, beneficio_cupom=None,
                         confianca=0.9)
        with patch("ofertas.sources.shopee.converter", return_value=oferta_mock), \
             patch("ofertas.grok.grok_service.analisar_texto", return_value=grok), \
             patch("ofertas.pipeline.postar_oferta", new_callable=AsyncMock), \
             patch.object(pipeline.publishing_controller, "pode_publicar",
                          return_value=(True, "ok", 0)):
            return asyncio.run(pipeline.processar_mensagem_telegram(
                texto=texto, source_id="@nerdofertas", message_id=message_id,
                bot=MagicMock()))

    def test_o_preco_do_texto_chega_na_oferta_publicada(self):
        """O caso real: conversor devolve preco None, o texto tem R$ 1.358, e a
        oferta precisa sair com 1358 -- senao o filtro de preco a descarta."""
        oferta_mock = Oferta(plataforma="shopee", id_produto="58255664210",
                             titulo="Oferta Shopee",
                             url_afiliado="https://s.shopee.com.br/4LJXIcT2Yq",
                             preco=None)
        res = self._roda(oferta_mock)

        self.assertTrue(res["ok"], res.get("motivo"))
        self.assertEqual(res["oferta"].preco, 1358.0)
        self.assertIsNone(res["oferta"].preco_original)
        self.assertIsNone(res["oferta"].desconto)

    def test_a_legenda_publicada_mostra_o_preco_do_texto(self):
        """Fecha o ciclo com o formatter: o que vai para o canal tem o valor."""
        from ofertas.formatter import montar_caption
        oferta_mock = Oferta(plataforma="shopee", id_produto="58255664210",
                             titulo="Oferta Shopee",
                             url_afiliado="https://s.shopee.com.br/4LJXIcT2Yq",
                             preco=None)
        res = self._roda(oferta_mock)
        legenda = montar_caption(res["oferta"])
        self.assertIn("1.358", legenda)
        self.assertNotIn("Oferta Shopee", legenda.split("\n")[1])

    def test_preco_da_plataforma_sobrevive_ao_pipeline(self):
        """A Amazon leu 89.90 na pagina; o texto dizia R$ 89. Quem consultou a
        fonte manda, e o preco da pagina e o do momento da compra."""
        oferta_mock = Oferta(plataforma="shopee", id_produto="58255664210",
                             titulo="Lava Loucas Brastemp",
                             url_afiliado="https://s.shopee.com.br/4LJXIcT2Yq",
                             preco=99.90, preco_original=1358.00)
        res = self._roda(oferta_mock)

        self.assertTrue(res["ok"], res.get("motivo"))
        self.assertEqual(res["oferta"].preco, 99.90)
        self.assertEqual(res["oferta"].preco_original, 1358.00)

    def test_oferta_sem_preco_e_sem_texto_e_recusada(self):
        """Sem preco de lado nenhum, continua recusada: nao se publica oferta
        sem valor."""
        oferta_mock = Oferta(plataforma="shopee", id_produto="58255664210",
                             titulo="Oferta Shopee",
                             url_afiliado="https://s.shopee.com.br/4LJXIcT2Yq",
                             preco=None)
        texto_sem_preco = ("\u27a1\ufe0f Lava Loucas Brastemp\n"
                           "https://s.shopee.com.br/3qNRstVRaQ\n")
        res = self._roda(oferta_mock, texto=texto_sem_preco, message_id=90311)

        self.assertFalse(res["ok"])
        self.assertEqual(res["motivo"], "filtrada: sem_preco")


if __name__ == "__main__":
    unittest.main(verbosity=2)
