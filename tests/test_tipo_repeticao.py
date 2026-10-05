"""Repetição por tipo de produto e janela de horário ativo.

O dedup por `uid` não pegava o que o canal sente: em produção (60 posts) nenhum
uid repetiu e nenhuma chave de título repetiu, e ainda assim o mesmo dia levou
três mochilas, duas bolas de pet, duas coleiras e duas creatinas — são produtos
de lojas diferentes, uids diferentes, e a mesma oferta para quem lê.

Aqui ficam as duas regras novas:

* equivalência — duas palavras significativas em comum E pelo menos 1/3 das
  palavras do título: é o mesmo produto com outro nome ("Batedor Misturador
  Elétrico" / "Batedor Mixer Elétrico");
* saturação — o mesmo tipo principal (primeira palavra) não sai mais de
  `MAX_REPETICOES_POR_TIPO` vezes na janela de cooldown.

E o relaxamento: se o cooldown esvaziar o lote, as ofertas barradas só por tipo
voltam. Canal mudo é pior que repetição.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import isolamento  # noqa: F401,E402

from ofertas import config as config_mod  # noqa: E402
from ofertas import db, pipeline  # noqa: E402
from ofertas.models import Oferta, tipo_principal, tokens_conteudo  # noqa: E402


def _oferta(titulo: str, produto: str = "1") -> Oferta:
    return Oferta(plataforma="shopee", id_produto=produto, titulo=titulo,
                  url_afiliado="", url_produto=f"https://shopee.com.br/item/{produto}",
                  preco=10.0)


class TestPalavrasSignificativas(unittest.TestCase):
    def test_tira_acento_numero_e_conectivo(self):
        self.assertEqual(
            tokens_conteudo("Mochila Impermeável 2 em 1 com Porta USB"),
            frozenset({"mochila", "impermeavel", "porta", "usb"}),
        )

    def test_tipo_principal_e_a_primeira_palavra_util(self):
        self.assertEqual(tipo_principal("Mochila Bolsa de Viagem"), "mochila")
        self.assertEqual(tipo_principal("ROMANTIC CROWN Mochila Viagem"), "romantic")
        self.assertEqual(tipo_principal("---"), "")

    def test_a_prova_dagua_nao_vira_identidade(self):
        """Dois produtos que só compartilham "à prova d'água" não são o mesmo."""
        camera = "Câmera IP A8 Icsee Infravermelho Prova D'água Wi-Fi"
        cabelo = "Conjunto de Retoque de Cabelo 2 em 1 à prova d'água"
        self.assertIsNone(
            pipeline._equivalente_a_postado(cabelo, [tokens_conteudo(camera)]),
            "propriedade compartilhada não pode virar bloqueio de repetição")


class TestEquivalencia(unittest.TestCase):
    def _bloqueia(self, novo: str, antigo: str) -> bool:
        return bool(pipeline._equivalente_a_postado(novo, [tokens_conteudo(antigo)]))

    def test_mesmo_produto_outro_anunciante(self):
        self.assertTrue(self._bloqueia(
            "Bola Inteligente Automatica Recarregavel Para Gato",
            "Bola de Rolamento Automatica Para Filhotes"))

    def test_mesmo_produto_com_nome_diferente(self):
        self.assertTrue(self._bloqueia(
            "Batedor Mixer Eletrico 2 em 1 Para Bebidas",
            "Batedor Misturador Eletrico 2 em 1 Taobiju Para Bebidas"))

    def test_uma_palavra_so_nao_bloqueia(self):
        self.assertFalse(self._bloqueia(
            "Furadeira de Impacto Eletrica 48V Sem Fio",
            "Batedor Misturador Eletrico 2 em 1 Para Bebidas"))

    def test_da_categoria_repete_tambem_e_bloqueia(self):
        """Dois teclados mecânicos na mesma janela é a repetição que dói.

        A regra é por tipo, não por anúncio: o usuário pediu para não ver
        "as mesmas coisas" e teclado mecânico é a mesma coisa mesmo em
        lojas e marcas diferentes.
        """
        self.assertTrue(self._bloqueia(
            "Teclado Gamer Semi-Mecanico RGB Anti-Ghosting",
            "Macaron Teclado Fidget Chaveiro ASMR Clicky Mecanico"))

    def test_palavra_generica_ao_lado_de_outra_nao_sustenta_bloqueio(self):
        self.assertFalse(self._bloqueia(
            "Garrafa Termica Inox 500ml",
            "Kit 2 Garrafas Termicas Inox Prata 500ml Com Estojo"))

    def test_titulo_sem_palavras_nao_bloqueia(self):
        self.assertIsNone(pipeline._equivalente_a_postado("!!!", [frozenset({"bola"})]))


class TestSaturacao(unittest.TestCase):
    def test_permite_ate_o_maximo_e_barra_o_proximo(self):
        contagem = {"mochila": db.MAX_REPETICOES_POR_TIPO}
        self.assertIsNotNone(pipeline._tipo_saturado("Mochila para Notebook", contagem))
        self.assertIsNone(pipeline._tipo_saturado(
            "Mochila para Notebook", {"mochila": db.MAX_REPETICOES_POR_TIPO - 1}))

    def test_tipo_diferente_nao_sofre_com_o_vizinho(self):
        contagem = {"mochila": db.MAX_REPETICOES_POR_TIPO}
        self.assertIsNone(pipeline._tipo_saturado("Bola de Rolamento Automatica", contagem))

    def test_titulo_sem_tipo_nao_eh_barrado(self):
        self.assertIsNone(pipeline._tipo_saturado("!!!", {"mochila": 99}))


class TestTiposRecentes(unittest.TestCase):
    def setUp(self):
        self.anterior = db.DB_PATH
        db.DB_PATH = Path(tempfile.mkdtemp(prefix="teste_tipos_")) / "ofertas.db"
        db.init_db()
        self.addCleanup(setattr, db, "DB_PATH", self.anterior)

    def _gravar(self, titulo: str, quando: datetime) -> None:
        with db._conn() as c:
            c.execute(
                "INSERT INTO postadas (uid, plataforma, titulo, preco, postada_em)"
                " VALUES (?, 'shopee', ?, 10.0, ?)",
                (titulo[:20] + str(abs(hash(titulo + str(quando))) % 10_000),
                 titulo, quando.isoformat(timespec="seconds")),
            )

    def test_somente_a_janela_entra(self):
        agora = datetime.now()
        self._gravar("Mochila de Viagem", agora - timedelta(hours=2))
        self._gravar("Bola de Pet", agora - timedelta(hours=80))
        palavras, contagem = db.tipos_recentes(48)

        self.assertEqual(len(palavras), 1, "bola de 80h não está na janela de 48h")
        self.assertEqual(contagem, {"mochila": 1})

    def test_data_invalida_nao_vira_bloqueio(self):
        with db._conn() as c:
            c.execute("INSERT INTO postadas (uid, titulo, postada_em)"
                      " VALUES ('x', 'Mochila Velha', 'nao-e-data')")
        palavras, contagem = db.tipos_recentes(48)

        self.assertEqual(palavras, [])
        self.assertEqual(contagem, {})

    def test_cooldown_zero_desliga(self):
        self._gravar("Mochila de Viagem", datetime.now())
        self.assertEqual(db.tipos_recentes(0), ([], {}))


class TestFiltrar(unittest.TestCase):
    def setUp(self):
        self.anterior = db.DB_PATH
        db.DB_PATH = Path(tempfile.mkdtemp(prefix="teste_filtrar_")) / "ofertas.db"
        db.init_db()
        self.addCleanup(setattr, db, "DB_PATH", self.anterior)

    def _filtrar(self, ofertas):
        with patch.object(pipeline.db, "preco_ultima_postagem", return_value=None), \
             patch.object(pipeline.db, "reservar", return_value=True), \
             patch.object(pipeline, "passes_product_filters", return_value=(True, "")):
            return pipeline.filtrar(ofertas)

    def test_tipo_ja_postado_nao_volta(self):
        hoje = datetime.now() - timedelta(hours=3)
        with db._conn() as c:
            c.execute("INSERT INTO postadas (uid, titulo, postada_em)"
                      " VALUES ('shopee:antiga', ?, ?)",
                      ("Bola de Rolamento Automatica Para Filhotes",
                       hoje.isoformat(timespec="seconds")))
        lote = [
            _oferta("Bola Inteligente Automatica Recarregavel Para Gato", "nova"),
            _oferta("Furadeira de Impacto 48V Sem Fio", "furadeira"),
        ]

        aprovadas = self._filtrar(lote)

        self.assertEqual([o.id_produto for o in aprovadas], ["furadeira"])

    def test_tipo_novo_no_ciclo_para_na_ter_dois_iguais(self):
        lote = [
            _oferta("Bola de Rolamento Automatica Para Filhotes", "a"),
            _oferta("Bola Inteligente Automatica Recarregavel Para Gato", "b"),
        ]

        aprovadas = self._filtrar(lote)

        self.assertEqual([o.id_produto for o in aprovadas], ["a"],
                         "o segundo do mesmo tipo tem de cair dentro do próprio ciclo")

    def test_lote_so_de_tipo_repetido_nao_deixa_o_canal_mudo(self):
        hoje = datetime.now() - timedelta(hours=1)
        with db._conn() as c:
            c.execute("INSERT INTO postadas (uid, titulo, postada_em)"
                      " VALUES ('shopee:antiga', ?, ?)",
                      ("Bola de Rolamento Automatica Para Filhotes",
                       hoje.isoformat(timespec="seconds")))
        lote = [
            _oferta("Bola Inteligente Automatica Recarregavel Para Gato", "b"),
            _oferta("Bola Inteligente Automatica Para Cao", "c"),
        ]

        aprovadas = self._filtrar(lote)

        self.assertEqual(len(aprovadas), 2,
                         "sem nada novo, o cooldown é relaxado em vez de calar o canal")

    def test_oferta_que_repetiu_so_por_tipo_ainda_passou_nos_filtros_de_qualidade(self):
        hoje = datetime.now() - timedelta(hours=1)
        with db._conn() as c:
            c.execute("INSERT INTO postadas (uid, titulo, postada_em)"
                      " VALUES ('shopee:antiga', ?, ?)",
                      ("Mochila Bolsa de Viagem Resistente Coreana",
                       hoje.isoformat(timespec="seconds")))
        lote = [_oferta("Mochila Impermeavel para Notebook com Porta USB", "b")]
        with patch.object(pipeline.db, "preco_ultima_postagem", return_value=None), \
             patch.object(pipeline.db, "reservar", return_value=True), \
             patch.object(pipeline, "passes_product_filters", return_value=(False, "nota baixa")):
            aprovadas = pipeline.filtrar(lote)

        self.assertEqual(aprovadas, [],
                         "repetição de tipo não pode reanimar oferta reprovada por qualidade")


class TestHorarioAtivo(unittest.TestCase):
    def test_janela_e_lida_em_brt(self):
        with patch.object(config_mod.config, "horario_ativo", "07:00-23:00"):
            self.assertTrue(config_mod.dentro_do_horario(datetime(2026, 1, 1, 7, 0)))
            self.assertTrue(config_mod.dentro_do_horario(datetime(2026, 1, 1, 22, 59)))
            self.assertFalse(config_mod.dentro_do_horario(datetime(2026, 1, 1, 23, 0)))
            self.assertFalse(config_mod.dentro_do_horario(datetime(2026, 1, 1, 6, 59)))

    def test_janela_virando_a_noite(self):
        with patch.object(config_mod.config, "horario_ativo", "22:00-02:00"):
            self.assertTrue(config_mod.dentro_do_horario(datetime(2026, 1, 1, 23, 30)))
            self.assertTrue(config_mod.dentro_do_horario(datetime(2026, 1, 1, 1, 30)))
            self.assertFalse(config_mod.dentro_do_horario(datetime(2026, 1, 1, 3, 0)))

    def test_sem_argumento_usa_a_hora_do_servidor_menos_tres(self):
        """O servidor roda em UTC; sem a conversão, "07:00-23:00" virava madrugada."""
        with patch.object(config_mod.config, "horario_ativo", "07:00-23:00"):
            esperado = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=3)
            dentro = config_mod.dentro_do_horario()
            self.assertEqual(dentro, config_mod.dentro_do_horario(esperado))

    def test_vazio_ou_formato_invalido_nao_bloqueia(self):
        with patch.object(config_mod.config, "horario_ativo", ""):
            self.assertTrue(config_mod.dentro_do_horario(datetime(2026, 1, 1, 3, 0)))
        with patch.object(config_mod.config, "horario_ativo", "sei-la"):
            self.assertTrue(config_mod.dentro_do_horario(datetime(2026, 1, 1, 3, 0)))


if __name__ == "__main__":
    unittest.main(verbosity=2)