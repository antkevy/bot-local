"""O link do Shopee tem de ser SEMPRE o nosso short link do MESMO item pedido.

O productOfferV2 usa itemId como filtro, não como garantia: a resposta pode
trazer outros itens na frente do item pedido. Regras cobertas aqui:

- se o item pedido está na resposta, a oferta sai do node dele (nunca nodes[0]
  de outro produto);
- se a resposta não traz o item pedido, NÃO se publica outro produto — cai no
  short link somente para a URL original do item;
- URL sem itemId (loja, cupom, categoria) não vira oferta — descartada.
- `e_id_produto` distingue item numérico de slug de página/loja.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from ofertas.sources import shopee  # noqa: E402


def node(item_id, nome="Produto", preco=10.0, link_fixo=None):
    return {
        "itemId": item_id,
        "productName": nome,
        "priceMin": str(preco),
        "priceMax": str(preco),
        "priceDiscountRate": "10",
        "imageUrl": "https://cf.shopee.com.br/img/1.jpg",
        "offerLink": link_fixo or f"https://s.shopee.com.br/ol_{item_id}",
        "productLink": f"https://shopee.com.br/product/1/{item_id}",
        "sales": 1200,
        "ratingStar": "4.8",
        "shopName": "Loja Teste",
    }


def resp_product(nodes):
    return {"productOfferV2": {"nodes": nodes}}


def resp_short(short="https://s.shopee.com.br/short_x"):
    return {"generateShortLink": {"shortLink": short}}


class TestConverterItemCerto(unittest.TestCase):
    def test_pega_o_node_do_item_pedido_mesmo_com_outro_na_frente(self):
        """Outro item vem primeiro na resposta; o pedido NÃO é trocado por ele."""
        def _chamar(query: str):
            if "productOfferV2" in query:
                return resp_product([node(999, "Outro Produto"), node(456, "Item Pedido")])
            return resp_short()

        with patch.object(shopee, "_chamar", side_effect=_chamar):
            oferta = shopee.converter("https://shopee.com.br/product/1/456")

        self.assertEqual(oferta.id_produto, "456")
        self.assertEqual(oferta.titulo, "Item Pedido")
        self.assertEqual(oferta.url_afiliado, "https://s.shopee.com.br/ol_456")

    def test_sem_o_item_na_resposta_nao_publica_outro_produto(self):
        """Resposta só com outros itens: vira short link do item pedido, nunca nodes[0]."""
        def _chamar(query: str):
            if "productOfferV2" in query:
                return resp_product([node(999, "Outro Produto")])
            return resp_short("https://s.shopee.com.br/short_456")

        with patch.object(shopee, "_chamar", side_effect=_chamar):
            oferta = shopee.converter("https://shopee.com.br/-i.1.456")

        self.assertEqual(oferta.id_produto, "456")
        self.assertEqual(oferta.url_afiliado, "https://s.shopee.com.br/short_456")

    def test_produto_fora_do_catalogo_gera_short_link(self):
        """Lista vazia na Open API: URL É de produto, então short link do item."""
        def _chamar(query: str):
            if "productOfferV2" in query:
                return resp_product([])
            return resp_short("https://s.shopee.com.br/short_456")

        with patch.object(shopee, "_chamar", side_effect=_chamar):
            oferta = shopee.converter("https://shopee.com.br/product/1/456")

        self.assertEqual(oferta.id_produto, "456")
        self.assertEqual(oferta.titulo, "Oferta Shopee")
        self.assertEqual(oferta.url_afiliado, "https://s.shopee.com.br/short_456")


class TestConverterShortLinkAfiliado(unittest.TestCase):
    """Short link de afiliado expande para um caminho da Shopee; só produto vira oferta.

    Produto aterrissa em https://shopee.com.br/opaanlp/<shop>/<item> (além de
    "..-i.<shop>.<item>" e "/product/<shop>/<item>"); cupom/slug aterrissa em
    /m/... e continua sendo descartado.
    """

    def _sessao_que_aterrissa_em(self, destino: str):
        class _Resp:
            url = destino

        class _Sessao:
            def get(self, *args, **kwargs):
                return _Resp()

        return _Sessao()

    def test_short_link_de_produto_em_opaanlp_gera_oferta(self):
        """O itemId vive na path /opaanlp/<shop>/<item>: não pode ser descartado."""
        def _chamar(query: str):
            if "productOfferV2" in query:
                return resp_product([node(58259487918, "Ar Condicionado 9000")])
            return resp_short("https://s.shopee.com.br/short_582")

        with patch.object(shopee, "sessao",
                          return_value=self._sessao_que_aterrissa_em(
                              "https://shopee.com.br/opaanlp/1207374375/58259487918?__mobile__=1")), \
             patch.object(shopee, "_chamar", side_effect=_chamar):
            oferta = shopee.converter("https://s.shopee.com.br/gQKZ2IeY3")

        self.assertEqual(oferta.id_produto, "58259487918")
        self.assertEqual(oferta.titulo, "Ar Condicionado 9000")
        self.assertEqual(oferta.url_afiliado, "https://s.shopee.com.br/ol_58259487918")

    def test_short_link_de_cupom_continua_descartado(self):
        """Cupom aterrissa em /m/cupom-de-desconto: segue sem itemId, sem oferta."""
        with patch.object(shopee, "sessao",
                          return_value=self._sessao_que_aterrissa_em(
                              "https://shopee.com.br/m/cupom-de-desconto")), \
             patch.object(shopee, "_chamar") as api:
            with self.assertRaises(RuntimeError):
                shopee.converter("https://s.shopee.com.br/6L560h8evB")

        api.assert_not_called()


class TestConverterSemItem(unittest.TestCase):
    def test_url_de_loja_sem_item_id_e_descartada(self):
        """Página de loja/cupom não tem itemId: NÃO vira oferta, nem chama a API."""
        with patch.object(shopee, "_chamar") as api:
            with self.assertRaises(RuntimeError):
                shopee.converter("https://shopee.com.br/espaco-tecnica")

        api.assert_not_called()

    def test_url_de_cupom_sem_item_id_e_descartada(self):
        with patch.object(shopee, "_chamar") as api:
            with self.assertRaises(RuntimeError):
                shopee.converter("https://shopee.com.br/m/desconto-10off")

        api.assert_not_called()


class TestEIdProduto(unittest.TestCase):
    def test_distingue_item_de_pagina(self):
        """Item numérico passa; slug de loja/página não."""
        self.assertTrue(shopee.e_id_produto("456"))
        self.assertFalse(shopee.e_id_produto("espaco-tecnica"))
        self.assertFalse(shopee.e_id_produto("cupom-de-desconto"))
        self.assertFalse(shopee.e_id_produto(""))
        self.assertFalse(shopee.e_id_produto(None))


if __name__ == "__main__":
    unittest.main()