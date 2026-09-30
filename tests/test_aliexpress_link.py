"""O link do AliExpress tem de ser SEMPRE o nosso afiliado apontando para o produto.

As APIs de produto (product.query e productdetail.get) devolviam um
`promotion_link` CONSTANTE e genérico (ex.: best.aliexpress.com) para produtos
diferentes — medido ao vivo com itens distintos. Por isso:

- `_item_para_oferta` NUNCA confia no promotion_link (deixa vazio);
- `converter` e `buscar_ofertas` SEMPRE geram o link do produto via
  aliexpress.affiliate.link.generate (gerar_link_afiliado), que resolve para o
  item exato com o aff_fcid do nosso tracking;
- sem link de afiliado gerado, o item não sai (fail-safe, sem chute).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from ofertas.sources import aliexpress  # noqa: E402

GENERICO = "https://s.click.aliexpress.com/s/pyFri10M6ltCONSTANTE"

CRED = ("app_key", "app_secret", "tracking_id", "https://api-sg.aliexpress.com/sync", "sha256")


def item_detalhe(pid: str, url: str) -> dict:
    return {
        "product_id": pid,
        "product_title": f"Produto {pid}",
        "product_detail_url": url,
        "target_sale_price": "12.99",
        "target_original_price": "25.99",
        "discount": "50%",
        "evaluate_rate": "96.0%",
        "product_main_image_url": "https://img.alicdn.com/kf/1.jpg",
        "promotion_link": GENERICO,
    }


def resposta(envoltorio: str, itens: list[dict]) -> dict:
    return {
        envoltorio: {
            "resp_result": {
                "result": {"products": {"product": itens}},
            }
        }
    }


class TestItemParaOferta(unittest.TestCase):
    def test_nunca_confia_no_promotion_link_da_api(self):
        """Mesmo com promotion_link genérico vindo cru, o campo sai vazio."""
        oferta = aliexpress._item_para_oferta(
            item_detalhe("1005008236561372", "https://pt.aliexpress.com/item/1005008236561372.html")
        )
        self.assertEqual(oferta.url_afiliado, "")
        self.assertTrue(oferta.url_produto.startswith("https://pt.aliexpress.com/item/"))

    def test_imagem_pequena_usada_quando_sem_principal(self):
        """Sem imagem principal, a primeira miniatura (lista) vira a imagem."""
        item = item_detalhe("1005008236561372", "https://pt.aliexpress.com/item/1005008236561372.html")
        item["product_main_image_url"] = ""
        item["product_small_image_urls"] = {"string": ["https://img.alicdn.com/kf/t1.jpg",
                                                       "https://img.alicdn.com/kf/t2.jpg"]}
        oferta = aliexpress._item_para_oferta(item)
        self.assertEqual(oferta.imagem, "https://img.alicdn.com/kf/t1.jpg")

    def test_imagem_pequena_texto_nao_vira_caractere(self):
        """Se `string` vier como TEXTO (e não lista), o [0] não pega o 1º caractere."""
        item = item_detalhe("1005008236561372", "https://pt.aliexpress.com/item/1005008236561372.html")
        item["product_main_image_url"] = ""
        item["product_small_image_urls"] = {"string": "https://img.alicdn.com/kf/thumb.jpg"}
        oferta = aliexpress._item_para_oferta(item)
        self.assertFalse(oferta.imagem)  # fica vazia; NUNCA "h" (1º caractere da URL)


class TestConverter(unittest.TestCase):
    def setUp(self):
        self.p_cred = patch.object(aliexpress, "_obter_credenciais", return_value=CRED)
        self.p_cred.start()
        self.addCleanup(self.p_cred.stop)

    def test_sempre_gera_o_link_do_produto_mesmo_com_promotion_link_presente(self):
        """Com produto no detalhe, o link SAI do link.generate, nunca do campo cru."""
        url_item = "https://pt.aliexpress.com/item/1005008236561372.html"
        chamadas: list[str] = []

        def _gera(url: str) -> str:
            chamadas.append(url)
            return "https://s.click.aliexpress.com/e/_c4OU6uId"

        with patch.object(aliexpress, "_chamar_api",
                          return_value=resposta("aliexpress_affiliate_productdetail_get_response",
                                                [item_detalhe("1005008236561372", url_item)])), \
             patch.object(aliexpress, "gerar_link_afiliado", side_effect=_gera) as gera:
            oferta = aliexpress.converter(url_item)

        self.assertEqual(oferta.url_afiliado, "https://s.click.aliexpress.com/e/_c4OU6uId")
        self.assertNotEqual(oferta.url_afiliado, GENERICO)
        self.assertEqual(chamadas, [url_item])
        gera.assert_called_once()

    def test_url_sem_item_id_e_descartada(self):
        """URL de vitrine/wholesale (sem item id) NÃO vira oferta — nada de chute."""
        with patch.object(aliexpress, "_chamar_api") as api, \
             patch.object(aliexpress, "gerar_link_afiliado") as gera:
            with self.assertRaises(RuntimeError):
                aliexpress.converter("https://pt.aliexpress.com/w/wholesale-x.html")

        api.assert_not_called()
        gera.assert_not_called()

    def test_fallback_so_para_url_de_produto(self):
        """Detalhe falhou mas a URL É de produto: link gerado do item, nunca da página."""
        url_item = "https://pt.aliexpress.com/item/1005008236561372.html"
        with patch.object(aliexpress, "_chamar_api",
                          return_value=resposta("aliexpress_affiliate_productdetail_get_response",
                                                [])), \
             patch.object(aliexpress, "gerar_link_afiliado",
                          return_value="https://s.click.aliexpress.com/e/_fallback") as gera:
            oferta = aliexpress.converter(url_item)

        self.assertEqual(oferta.url_afiliado, "https://s.click.aliexpress.com/e/_fallback")
        self.assertEqual(oferta.id_produto, "1005008236561372")
        gera.assert_called_once_with(url_item)

    def test_sem_link_de_afiliado_nao_converte(self):
        """Se o link.generate falhar, o converter não devolve oferta (nada de link cru)."""
        with patch.object(aliexpress, "_chamar_api",
                          return_value=resposta("aliexpress_affiliate_productdetail_get_response",
                                                [item_detalhe("1005008236561372",
                                                              "https://pt.aliexpress.com/item/1005008236561372.html")])), \
             patch.object(aliexpress, "gerar_link_afiliado",
                          side_effect=RuntimeError("API do AliExpress falhou")):
            with self.assertRaises(RuntimeError):
                aliexpress.converter("https://pt.aliexpress.com/item/1005008236561372.html")


class TestEIdProduto(unittest.TestCase):
    def test_distingue_produto_de_pagina(self):
        """Id numérico de produto passa; slug de vitrine/wholesale/cupom não."""
        self.assertTrue(aliexpress.e_id_produto("1005008236561372"))
        self.assertFalse(aliexpress.e_id_produto("wholesale-x"))
        self.assertFalse(aliexpress.e_id_produto("espaco-tecnica"))
        self.assertFalse(aliexpress.e_id_produto(""))
        self.assertFalse(aliexpress.e_id_produto(None))


class TestBuscarOfertas(unittest.TestCase):
    def setUp(self):
        self.p_cfg = patch.object(aliexpress.config, "fonte_aliexpress",
                                  {"buscas": ["fone"]}, create=True)
        self.p_cfg.start()
        self.p_cred = patch.object(aliexpress, "_obter_credenciais", return_value=CRED)
        self.p_cred.start()
        self.addCleanup(self.p_cfg.stop)
        self.addCleanup(self.p_cred.stop)

    def test_gera_link_por_produto_e_ignora_quem_nao_conseguir(self):
        itens = [
            item_detalhe("1005000000001", "https://pt.aliexpress.com/item/1005000000001.html"),
            item_detalhe("1005000000002", "https://pt.aliexpress.com/item/1005000000002.html"),
            item_detalhe("1005000000003", "https://pt.aliexpress.com/item/1005000000003.html"),
        ]
        links = {
            "https://pt.aliexpress.com/item/1005000000001.html": "https://s.click.aliexpress.com/e/_L1",
            "https://pt.aliexpress.com/item/1005000000002.html": "https://s.click.aliexpress.com/e/_L2",
        }

        def _gera(url: str) -> str:
            if url not in links:
                raise RuntimeError("sem comissão disponível")
            return links[url]

        with patch.object(aliexpress, "_chamar_api",
                          return_value=resposta("aliexpress_affiliate_product_query_response", itens)), \
             patch.object(aliexpress, "gerar_link_afiliado", side_effect=_gera):
            ofertas = aliexpress.buscar_ofertas()

        por_id = {o.id_produto: o for o in ofertas}
        self.assertEqual(set(por_id), {"1005000000001", "1005000000002"})
        self.assertEqual(por_id["1005000000001"].url_afiliado, "https://s.click.aliexpress.com/e/_L1")
        self.assertEqual(por_id["1005000000002"].url_afiliado, "https://s.click.aliexpress.com/e/_L2")
        for oferta in ofertas:
            self.assertNotEqual(oferta.url_afiliado, GENERICO)
            self.assertNotEqual(oferta.url_afiliado, "")


if __name__ == "__main__":
    unittest.main()