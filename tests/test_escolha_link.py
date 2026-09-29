"""Escolha do link de produto dentro de uma mensagem.

O NERD OFERTAS nao poe o link do produto primeiro. Das 25 mensagens lidas, em
todas a ordem e a mesma: primeiro um link de loja (`espaco-tecnologia`,
`cupom-de-desconto`), depois o produto (`58255664210`).

O pipeline usava `links_marketplace[0]`, entao as 6 mensagens de teste saiam
com o mesmo uid `shopee:espaco-tecnologia`. O dedup, que esta certo em se
mesmo, via as cinco seguintes como `produto_ja_postado`: 1 post de 6 ofertas,
e as 5 descartadas sem aparecer no log como erro.
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
# no data/cadencia.json de verdade. Foi ela que, sozinha, encheu o arquivo com
# 10 registros de um teste e travou a publicação do bot.
import isolamento  # noqa: F401,E402

from ofertas.models import Oferta
from ofertas.pipeline import MAX_LINKS_POR_MENSAGEM
from ofertas.sources import amazon, mercadolivre, shopee
from ofertas.sources.telegram_scraper import pre_processar_mensagem

# URL de loja e URL de produto, como aparecem na mesma mensagem do canal.
URL_LOJA = "https://s.shopee.com.br/3qNRstVRaQ"
URL_PRODUTO = "https://s.shopee.com.br/4LJXIcT2Yq"

MSG_DOIS_LINKS = (
    "\u27a1\ufe0f Lava Loucas Brastemp 8 Servicos\n\n"
    "\u2705 R$ 1.358 \U0001f631\U0001f631\n\n"
    f"{URL_LOJA}\n"
    f"{URL_PRODUTO}\n"
)


def _oferta(id_produto: str, preco=None, titulo="Oferta Shopee") -> Oferta:
    return Oferta(plataforma="shopee", id_produto=id_produto, titulo=titulo,
                  url_afiliado="https://s.shopee.com.br/x", preco=preco)


def _loja() -> Oferta:
    """O que o `converter` devolve para um link de loja: slug e titulo generico."""
    return _oferta("espaco-tecnologia")


def _produto() -> Oferta:
    return _oferta("58255664210", preco=1358.0, titulo="Lava Loucas Brastemp 8 Servicos")


class TestEIdProduto(unittest.TestCase):
    """Cada plataforma declara se o id que ela montou e de um produto."""

    def test_shopee_somente_id_numerico(self):
        """A slug da loja e o que o `converter` inventa quando `_RE_IDS` falha."""
        self.assertTrue(shopee.e_id_produto("58255664210"))
        for slug in ("espaco-tecnologia", "cupom-de-desconto", "", None):
            with self.subTest(slug=slug):
                self.assertFalse(shopee.e_id_produto(slug))

    def test_shopee_id_nao_numerico_nao_passa_so_por_ter_digito(self):
        self.assertFalse(shopee.e_id_produto("abc123"))
        self.assertFalse(shopee.e_id_produto("123-456"))

    def test_amazon_exige_asin_de_10_caracteres(self):
        self.assertTrue(amazon.e_id_produto("B09SGPQ2J7"))
        for ruim in ("B09NnFj0N", "espaco-tecnologia", "", None):
            with self.subTest(ruim=ruim):
                self.assertFalse(amazon.e_id_produto(ruim))

    def test_mercadolivre_exige_mlb(self):
        self.assertTrue(mercadolivre.e_id_produto("MLB18725310"))
        for ruim in ("cupom-de-desconto", "MLB-", "", None):
            with self.subTest(ruim=ruim):
                self.assertFalse(mercadolivre.e_id_produto(ruim))

    def test_as_mensagens_reais_do_canal_sao_classificadas_certo(self):
        """O par que a medicao encontrou: primeiro slug, depois id numerico."""
        self.assertFalse(shopee.e_id_produto("espaco-tecnologia"))
        self.assertFalse(shopee.e_id_produto("cupom-de-desconto"))
        self.assertTrue(shopee.e_id_produto("58255664210"))


class TestPreProcessarOrdenaOsLinks(unittest.TestCase):
    """Pre-requisito do resto: os dois URLs precisam chegar em ordem known."""

    def test_a_mensagem_real_tem_os_dois_links(self):
        pre = pre_processar_mensagem(MSG_DOIS_LINKS)
        urls = [l["url"] for l in pre["links_marketplace"]]
        self.assertEqual(urls, [URL_LOJA, URL_PRODUTO])
        self.assertEqual(len(urls), 2)


class TestEscolhaDoLink(unittest.TestCase):
    """O pipeline inteiro, com so o `converter` e a IA simulados."""

    def setUp(self):
        from ofertas import db
        self.banco_anterior = db.DB_PATH
        db.DB_PATH = Path(tempfile.mkdtemp(prefix="teste_escolha_")) / "ofertas.db"
        db.init_db()

    def tearDown(self):
        from ofertas import db
        db.DB_PATH = self.banco_anterior

    def _roda(self, por_url, texto=MSG_DOIS_LINKS, message_id=700) -> dict:
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch
        from ofertas import pipeline
        from ofertas.grok import GrokResult

        grok = GrokResult(tipo="produto",
                         titulo_otimizado="Lava Loucas Brastemp 8 Servicos",
                         tem_cupom=False, cupom=None, beneficio_cupom=None,
                         confianca=0.9)
        with patch("ofertas.sources.shopee.converter", side_effect=por_url) as conv, \
             patch("ofertas.grok.grok_service.analisar_texto", return_value=grok), \
             patch("ofertas.pipeline.postar_oferta", new_callable=AsyncMock), \
             patch.object(pipeline.publishing_controller, "pode_publicar",
                          return_value=(True, "ok", 0)):
            res = asyncio.run(pipeline.processar_mensagem_telegram(
                texto=texto, source_id="@nerdofertas", message_id=message_id,
                bot=MagicMock()))
        res["_convertidos"] = [c.args[0] for c in conv.call_args_list]
        return res

    def test_usa_o_link_de_produto_e_nao_o_de_loja(self):
        res = self._roda(lambda url: _loja() if url == URL_LOJA else _produto())

        self.assertTrue(res["ok"], res.get("motivo"))
        self.assertEqual(res["oferta"].uid, "shopee:58255664210")
        self.assertEqual(res["oferta"].preco, 1358.0)

    def test_o_uid_nao_repete_entre_produtos_da_mesma_mensagem_padrao(self):
        """A regressao que motivou tudo: dois produtos, o mesmo uid."""
        res = self._roda(lambda url: _loja() if url == URL_LOJA else _produto())
        self.assertNotEqual(res["oferta"].uid, "shopee:espaco-tecnologia")

    def test_um_post_so_onde_antes_ia_um(self):
        """Duas mensagens de produto precisam gerar dois uids, para o dedup nao
        engolir a segunda como repetida."""
        res1 = self._roda(lambda url: _loja() if url == URL_LOJA else _produto(),
                          message_id=700)
        res2 = self._roda(
            lambda url: (_oferta("22498473548", 1246.0, "Cervejeira")
                         if url == URL_PRODUTO else _loja()),
            message_id=701)
        self.assertTrue(res1["ok"], res1.get("motivo"))
        self.assertTrue(res2["ok"], res2.get("motivo"))
        self.assertNotEqual(res1["oferta"].uid, res2["oferta"].uid)

    def test_nao_testa_mais_links_que_o_teto(self):
        """Um limite de rede: mensagem com 4 links nao vira varredura."""
        texto = MSG_DOIS_LINKS + "".join(
            f"https://s.shopee.com.br/extr{i}\n" for i in range(3))
        res = self._roda(lambda url: _loja(), texto=texto)
        self.assertEqual(len(res["_convertidos"]), MAX_LINKS_POR_MENSAGEM)

    def test_caminho_ate_o_teto_pode_encontrar_o_produto(self):
        """O produto no terceiro link ainda e achado."""
        texto = MSG_DOIS_LINKS + "https://s.shopee.com.br/ultimo\n"
        res = self._roda(
            lambda url: _produto() if url == "https://s.shopee.com.br/ultimo" else _loja(),
            texto=texto)
        self.assertTrue(res["ok"], res.get("motivo"))
        self.assertEqual(res["oferta"].uid, "shopee:58255664210")

    def test_sem_nenhum_link_de_produto_usa_a_primeira_conversao(self):
        """Melhor uma oferta a deriva do que sumir com a mensagem: quem decide
        se ela serve continua sendo o filtro de preco e os demais."""
        res = self._roda(lambda url: _loja())

        self.assertTrue(res["ok"], res.get("motivo"))
        self.assertEqual(res["oferta"].uid, "shopee:espaco-tecnologia")
        # Sem preco no conversor, o texto da mensagem preenche.
        self.assertEqual(res["oferta"].preco, 1358.0)

    def test_o_texto_so_uma_vez_e_com_o_link_escolhido(self):
        """O preco vem da mensagem, o produto vem do link certo: as duas coisas
        precisam valer para a mesma oferta."""
        res = self._roda(lambda url: _loja() if url == URL_LOJA else _produto())
        self.assertEqual(res["oferta"].uid, "shopee:58255664210")
        self.assertEqual(res["oferta"].preco, 1358.0)

    def test_link_que_levanta_excecao_nao_derruba_os_outros(self):
        def por_url(url):
            if url == URL_LOJA:
                raise RuntimeError("Shopee API: erro de rede")
            return _produto()

        res = self._roda(por_url)
        self.assertTrue(res["ok"], res.get("motivo"))
        self.assertEqual(res["oferta"].uid, "shopee:58255664210")

    def test_todos_os_links_falhando_nao_publica_nada(self):
        res = self._roda(lambda url: None)
        self.assertFalse(res["ok"])
        self.assertEqual(res["motivo"], "sem_produto")


if __name__ == "__main__":
    unittest.main(verbosity=2)
