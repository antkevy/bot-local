"""A aba Links agora mostra a foto do produto, o link original e o que foi
convertido para afiliado.

O banco `postadas` sempre guardou `imagem` e `url_afiliado`, mas NÃO o link
original (`url_produto`) — sem ele não há como mostrar "o que foi convertido"
no painel. Este teste trava o caminho inteiro, da gravação à exposição:

- `registrar()` guarda o link original junto com o afiliado;
- `listar_postadas()` devolve os dois;
- `obter_metricas()` expõe `imagem` e `url_original` na lista da aba Links.

Posts anteriores à mudança não têm original: ficam com `url_original` vazio –
nada de inventar link, a foto e o afiliado continuam aparecendo.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from ofertas import db
from ofertas.models import Oferta


def _oferta_com_original() -> Oferta:
    return Oferta(
        plataforma="shopee",
        id_produto="58255664210",
        titulo="Lava Loucas Brastemp 8 Servicos",
        preco=1358.0,
        url_produto="https://shopee.com.br/product/58255664210",
        url_afiliado="https://s.shopee.com.br/afiliado",
        imagem="https://down-br.img.susercontent.com/file/abc",
    )


def _insere_post_antigo() -> None:
    """Grava como o bot antigo gravava: sem a coluna url_produto (NULL)."""
    import datetime as dt

    with db._conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO postadas"
            " (uid, plataforma, titulo, preco, url_afiliado, imagem, postada_em)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("amazon:B09SGPQ2J7", "amazon", "Kindle 11a geração", 299.0,
             "https://www.amazon.com.br/dp/B09SGPQ2J7?tag=afiliado-20", "",
             dt.datetime.now().isoformat(timespec="seconds")),
        )


class TestAbaLinks(unittest.TestCase):
    def setUp(self):
        self.banco_anterior = db.DB_PATH
        db.DB_PATH = Path(tempfile.mkdtemp(prefix="teste_aba_links_")) / "ofertas.db"
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.banco_anterior

    def test_registrar_guarda_original_e_listar_devolve(self):
        db.registrar(_oferta_com_original())
        linha = db.listar_postadas(10)[0]
        self.assertEqual(linha["url_produto"],
                         "https://shopee.com.br/product/58255664210")
        self.assertEqual(linha["imagem"],
                         "https://down-br.img.susercontent.com/file/abc")
        self.assertEqual(linha["url_afiliado"], "https://s.shopee.com.br/afiliado")

    def test_post_antigo_sem_original_fica_none_e_nao_quebra(self):
        """Coluna só criada depois = NULL, nunca um link inventado."""
        _insere_post_antigo()
        linha = db.listar_postadas(10)[0]
        self.assertIsNone(linha["url_produto"])
        self.assertEqual(linha["url_afiliado"],
                         "https://www.amazon.com.br/dp/B09SGPQ2J7?tag=afiliado-20")

    def test_obter_metricas_mostra_imagem_e_original_na_aba(self):
        from ofertas.painel import obter_metricas
        db.registrar(_oferta_com_original())
        links = obter_metricas()["links_recentes"]
        self.assertEqual(len(links), 1)
        l = links[0]
        self.assertEqual(l["url"], "https://s.shopee.com.br/afiliado")
        self.assertEqual(l["url_original"],
                         "https://shopee.com.br/product/58255664210")
        self.assertEqual(l["imagem"],
                         "https://down-br.img.susercontent.com/file/abc")

    def test_obter_metricas_post_antigo_expoe_vazio_sem_afetar_o_afiliado(self):
        from ofertas.painel import obter_metricas
        _insere_post_antigo()
        l = obter_metricas()["links_recentes"][0]
        self.assertEqual(l["url_original"], "")
        self.assertEqual(l["imagem"], "")
        self.assertEqual(l["url"],
                         "https://www.amazon.com.br/dp/B09SGPQ2J7?tag=afiliado-20")


if __name__ == "__main__":
    unittest.main(verbosity=2)