"""Os parsers das fontes passaram a preencher nota e vendas — quando a fonte
realmente entrega esses números, e nunca inventando.

Antes, `avaliacao` e `vendas` nasciam sempre None: a Shopee espremia a nota e
as vendas num texto solto de `extra`, o Mercado Livre idem, e a Amazon notava
a estrela mas também como texto. O formatador já sabia escrever "⭐ 4.8 ·
🛒 18.143 vendidos", o modelo já tinha os campos, o poster já mandava a foto.
Só o dado nunca chegava — e ninguém percebia, porque o post saía bonito
mesmo sem os selos.

O que estes testes defendem é o contrário do que a intuição manda: não é
"preencher sempre", é "preencher quando dá e devolver None quando não dá".
O '0' que a loja manda em vez de nota, o '1.2k' com sufixo, a nota 9.9 — tudo
isso tem que virar None. Um número fora da faixa vira selo mentiroso na
publicação, e é pior do que nenhum selo.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from ofertas.formatter import montar_caption  # noqa: E402
from ofertas.sources import amazon, mercadolivre, shopee  # noqa: E402
from ofertas.sources.mercadolivre import _avaliacao_e_vendas  # noqa: E402

# os valores que a Open API da Shopee entrega de verdade, medidos numa busca
# real: nota como string '4.8', vendas como int. Nada abaixo é inventado.
NO_REAL = {
    "itemId": 1006215031,
    "productName": "Fone Bluetooth Sem Fio TWS X55",
    "priceMin": 1513,
    "priceDiscountRate": 29,
    "imageUrl": "https://down-br.img.susercontent.com/file/abc",
    "ratingStar": "4.8",
    "sales": 18143,
}


class TestShopee(unittest.TestCase):
    def test_nota_e_vendas_entram_nos_campos_estruturados(self):
        o = shopee._node_para_oferta(NO_REAL)
        self.assertEqual(o.avaliacao, 4.8)
        self.assertEqual(o.vendas, 18143)
        self.assertIsNone(o.extra, "nota e vendas saíram de `extra`: repetem na legenda")

    def test_a_legenda_escreve_o_selo_uma_vez_so(self):
        o = shopee._node_para_oferta(NO_REAL)
        caption = montar_caption(o)
        self.assertIn("⭐ 4.8 · 🛒 18.143 vendidos", caption)
        self.assertEqual(caption.count("⭐"), 1,
                         "a nota repetida na legenda (selo + texto de extra)")
        self.assertEqual(caption.count("18.143"), 1)

    def test_nota_zero_vira_none_para_nao_publicar_estrela_inventada(self):
        o = shopee._node_para_oferta({**NO_REAL, "ratingStar": "0", "sales": 0})
        self.assertIsNone(o.avaliacao)
        self.assertIsNone(o.vendas)
        self.assertNotIn("⭐ 0", montar_caption(o))

    def test_nota_fora_da_faixa_vira_none(self):
        o = shopee._node_para_oferta({**NO_REAL, "ratingStar": "9.9"})
        self.assertIsNone(o.avaliacao)

    def test_vendas_com_sufixo_nao_e_inventado(self):
        # '1.2k' é uma abreviação, não um número: converter viraria chute.
        o = shopee._node_para_oferta({**NO_REAL, "sales": "1.2k"})
        self.assertIsNone(o.vendas)


CARD_AMAZON = (
    '<div data-asin="B0X1234567">'
    "  <h2>Fone Bluetooth TWS</h2>"
    '  <div class="a-price"><span class="a-offscreen">R$&nbsp;99,90</span></div>'
    '  <span class="a-icon-alt">4,8 de 5 estrelas</span>'
    '  <i class="a-icon-prime"></i>'
    '  <img class="s-image" src="https://m.media-amazon.com/images/I/51abc.jpg">'
    "  Mais vendido"
    "</div>"
)


class TestAmazon(unittest.TestCase):
    def test_nota_com_virgula_brasileira_vira_4_8(self):
        soup = BeautifulSoup(CARD_AMAZON, "lxml")
        card = soup.select_one("div[data-asin]")
        self.assertEqual(amazon._nota_do_card(card), 4.8)

    def test_nota_com_ponto_nao_vira_48(self):
        soup = BeautifulSoup(CARD_AMAZON.replace("4,8", "4.8"), "lxml")
        card = soup.select_one("div[data-asin]")
        self.assertEqual(amazon._nota_do_card(card), 4.8)

    def test_card_sem_nota_devolve_none(self):
        soup = BeautifulSoup(CARD_AMAZON.replace('<span class="a-icon-alt">4,8 de 5 estrelas</span>', ""),
                             "lxml")
        card = soup.select_one("div[data-asin]")
        self.assertIsNone(amazon._nota_do_card(card))

    def test_card_completo_preenche_nota_e_nao_repte_estrela_no_extra(self):
        o = amazon._card_para_oferta(BeautifulSoup(CARD_AMAZON, "lxml").select_one("div[data-asin]"))
        self.assertIsNotNone(o)
        self.assertEqual(o.avaliacao, 4.8)
        self.assertIsNone(o.vendas, "Amazon não mostra vendidos; o campo tem que ficar None")
        self.assertNotIn("⭐", o.extra or "")
        self.assertIn("Prime", o.extra or "")


def _card_ml(texto_review: str, pix: str = "") -> BeautifulSoup:
    """Card de oferta do ML no formato medido: nota e vendas num bloco junto."""
    html = (
        f'<div class="poly-card">'
        f'  <a class="poly-component__title" '
        f'     href="https://www.mercadolivre.com.br/brinquedo-escavadeira-2in1/p/MLB43890280">'
        f"    Escavadeira 2in1</a>"
        f'  <div class="poly-price__current">'
        f'    <span class="andes-money-amount__fraction">123</span>'
        f'    <span class="andes-money-amount__cents">45</span></div>'
        f'  <img class="poly-component__picture" src="https://http2.mlstatic.com/D_Q_NP_2X_1-AB.webp">'
        f'  <div class="poly-component__review-compacted">{texto_review}</div>'
        f'  <div class="poly-price__unit-description">{pix}</div>'
        f"  Frete grátis"
        f"</div>"
    )
    return BeautifulSoup(html, "lxml").select_one("div.poly-card")


class TestMercadoLivre(unittest.TestCase):
    def test_review_sem_mil(self):
        card = _card_ml("4.9 | +1000 vendidos")
        self.assertEqual(_avaliacao_e_vendas(card), (4.9, 1000))

    def test_review_com_mil_multiplica_por_mil(self):
        card = _card_ml("4.8 | +10mil vendidos")
        self.assertEqual(_avaliacao_e_vendas(card), (4.8, 10000))

    def test_review_so_com_nota(self):
        card = _card_ml("4.9")
        self.assertEqual(_avaliacao_e_vendas(card), (4.9, None))

    def test_card_sem_review(self):
        card = _card_ml("")
        self.assertEqual(_avaliacao_e_vendas(card), (None, None))

    def test_vendas_duzentos_mil(self):
        card = _card_ml("4.7 | +250mil vendidos")
        self.assertEqual(_avaliacao_e_vendas(card), (4.7, 250000))

    def test_parse_card_completo(self):
        card = _card_ml("4.7 | +50mil vendidos")
        o = mercadolivre._parse_card(card)
        self.assertIsNotNone(o)
        self.assertEqual(o.avaliacao, 4.7)
        self.assertEqual(o.vendas, 50000)
        self.assertEqual(o.preco, 123.45)
        self.assertIsNone(o.extra, "Frete/Pix do card não entram mais na postagem")
        self.assertNotIn("⭐", o.extra or "")
        caption = montar_caption(o)
        self.assertIn("⭐ 4.7 · 🛒 50.000 vendidos", caption)
        self.assertEqual(caption.count("⭐"), 1)

    def test_parse_card_nao_anuncia_frete_nem_pix(self):
        """'Frete grátis' e 'no Pix' presentes no card não viram postagem."""
        card = _card_ml("4.7 | +50mil vendidos", pix="no Pix")
        o = mercadolivre._parse_card(card)
        self.assertIsNone(o.extra)
        caption = montar_caption(o)
        self.assertNotIn("Frete", caption)
        self.assertNotIn("Pix", caption)
        self.assertNotIn("🚚", caption)

    def test_preco_sem_original_diz_por_e_nao_moeda(self):
        """Sem preço 'De', o valor aparece como '✅ Por: R$ 123,45', não '💰'."""
        o = mercadolivre._parse_card(_card_ml("4.7 | +50mil vendidos"))
        caption = montar_caption(o)
        self.assertIn("✅ Por: <b>R$ 123,45</b>", caption)
        self.assertNotIn("💰", caption)


if __name__ == "__main__":
    unittest.main()