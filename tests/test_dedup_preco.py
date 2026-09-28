"""Duas-promessas, uma bateria: a mesma oferta não sai duas vezes, e o preço
que vai ao ar é o preço que foi coletado.

Os dois problemas nasceram do mesmo lugar — uma janela de tempo entre "deixa eu
publicar?" (`ja_postada`) e "publiquei" (`registrar`). Nessa janela cabe a
geração de link de afiliado no navegador, que leva segundos. Com quatro
instâncias do bot no ar, todas as quatro passaram no `ja_postada` antes de
qualquer uma registrar, e a mesma oferta foi ao ar quatro vezes.

Fechar isso deu três peças, e cada uma tem um teste aqui:

1. reserva por oferta no SQLite (`db.reservar`) — transforma a checagem em
   escrita, fechando a corrida;
2. devolução da reserva quando a oferta não é publicada — senão a trava vira
   perda de oferta, que é o outro extremo do mesmo bug;
3. releitura do preço na hora de publicar a pendência do ML — o preço foi lido
   quando a oferta foi coletada e pode ter mudado no tempo de esperar o login.

O banco usado aqui é temporário (o `setUp` troca `db.DB_PATH`), porque
`tests/test_isolamento_dados.py` provou que suíte que escreve no banco real
apaga o histórico do usuário.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from bs4 import BeautifulSoup

from ofertas import db, pipeline
from ofertas.config import config
from ofertas.filters import passes_product_filters
from ofertas.formatter import montar_caption
from ofertas.models import Oferta
from ofertas.sources import mercadolivre
from ofertas.sources.ml_auth import ml_auth_service

FIXTURE_PRECOS = Path(__file__).resolve().parent / "fixtures" / "ml_precos_reais.json"


def gerar_links(ofertas, bot=None):
    """Substituto do gerador real: preenche o link que a linha do banco não tem.

    A pendência é reconstruída a partir das colunas salvas, e nenhuma delas é o
    link de afiliado — quem escreve é o gerador. Um no-op aqui faria o serviço
    sair por "sem link de afiliado" e o teste não veria nada do que quer medir.
    """
    for o in ofertas:
        o.url_afiliado = f"https://goto/afiliado/{o.id_produto}"
    return None


def oferta_de_teste(plataforma="shopee", id_produto="1", preco=50.0, **extra) -> Oferta:
    return Oferta(
        plataforma=plataforma,
        id_produto=id_produto,
        titulo=extra.pop("titulo", f"Produto de teste {id_produto} com titulo razoavelmente longo"),
        preco=preco,
        avaliacao=4.5,
        vendas=500,
        **extra,
    )


class BancoTemporario(unittest.TestCase):
    """Cada teste roda contra um banco novo: nenhum estado vaza para o outro."""

    def setUp(self):
        self.banco_anterior = db.DB_PATH
        self.pasta = tempfile.mkdtemp(prefix="teste_dedup_")
        db.DB_PATH = Path(self.pasta) / "ofertas.db"
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.banco_anterior


# ─────────────────────────────────────────────────────────────────────
# 1. A reserva: fecha a janela entre "deixa eu publicar?" e "publiquei"
# ─────────────────────────────────────────────────────────────────────

class TestReserva(unittest.TestCase):
    def setUp(self):
        self.banco_anterior = db.DB_PATH
        self.pasta = tempfile.mkdtemp(prefix="teste_reserva_")
        db.DB_PATH = Path(self.pasta) / "ofertas.db"
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.banco_anterior

    def test_a_segunda_reserva_da_mesma_oferta_e_negada(self):
        self.assertTrue(db.reservar("shopee:1"), "a primeira reserva tem de passar")
        self.assertFalse(db.reservar("shopee:1"),
                         "a segunda reserva da mesma oferta tem de ser negada")

    def test_ofertas_diferentes_nao_se_atrapan(self):
        self.assertTrue(db.reservar("shopee:1"))
        self.assertTrue(db.reservar("shopee:2"))

    def test_esta_reservada_reflete_o_ciclo(self):
        self.assertFalse(db.esta_reservada("shopee:1"))
        db.reservar("shopee:1")
        self.assertTrue(db.esta_reservada("shopee:1"))
        db.liberar_reserva("shopee:1")
        self.assertFalse(db.esta_reservada("shopee:1"))

    def test_registrar_consome_a_reserva(self):
        """Reserva que sobrevive à postagem trava a oferta até o TTL."""
        db.reservar("shopee:1")
        db.registrar(oferta_de_teste(id_produto="1", preco=50.0))
        self.assertFalse(db.esta_reservada("shopee:1"),
                         "a reserva tem de sumir junto com a postagem")
        self.assertTrue(db.ja_postada("shopee:1", 7))

    def test_ja_ou_reservada_cobre_postada_e_reservada(self):
        self.assertFalse(db.ja_ou_reservada("shopee:1", 7))
        db.reservar("shopee:1")
        self.assertTrue(db.ja_ou_reservada("shopee:1", 7),
                        "reservada ainda não foi postada, mas já está em uso")
        db.registrar(oferta_de_teste(id_produto="1"))
        self.assertTrue(db.ja_ou_reservada("shopee:1", 7))

    def test_reserva_de_processo_morto_e_ignorada(self):
        """Se o processo cai no meio da publicação, a oferta não fica presa.

        Sem isto, uma queda do bot deixaria a oferta bloqueada pelo TTL
        inteiro — trocaria post repetida por oferta perdida.
        """
        with db._conn() as c:
            c.execute(
                "INSERT INTO reservas (uid, reservado_em, pid) VALUES (?, ?, ?)",
                ("shopee:1", dt.datetime.now().isoformat(timespec="seconds"), 999999),
            )
        # PID 999999 quase certamente não existe; e mesmo se existir, a
        # verificação passa pela identidade do processo (PID + hora de criação).
        self.assertFalse(db.esta_reservada("shopee:1"),
                         "reserva de processo morto não pode travar a oferta")
        self.assertTrue(db.reservar("shopee:1"))

    def test_reserva_vencida_pelo_ttl_e_ignorada(self):
        with db._conn() as c:
            velha = (dt.datetime.now() - dt.timedelta(hours=3)).isoformat(timespec="seconds")
            c.execute(
                "INSERT INTO reservas (uid, reservado_em, pid) VALUES (?, ?, ?)",
                ("shopee:1", velha, os.getpid()),
            )
        self.assertFalse(db.esta_reservada("shopee:1", ttl=600))
        self.assertTrue(db.reservar("shopee:1", ttl=600))

    def test_limpar_reservas_vencidas_conta_so_as_mortas(self):
        agora = dt.datetime.now().isoformat(timespec="seconds")
        velha = (dt.datetime.now() - dt.timedelta(hours=3)).isoformat(timespec="seconds")
        with db._conn() as c:
            # Viva: processo real (este) e dentro do TTL.
            c.execute("INSERT INTO reservas (uid, reservado_em, pid) VALUES (?, ?, ?)",
                      ("shopee:1", agora, os.getpid()))
            # Morta: TTL vencido.
            c.execute("INSERT INTO reservas (uid, reservado_em, pid) VALUES (?, ?, ?)",
                      ("shopee:2", velha, os.getpid()))
            # Morta: dono que não existe mais, TTL ainda dentro.
            c.execute("INSERT INTO reservas (uid, reservado_em, pid) VALUES (?, ?, 999999)",
                      ("shopee:3", agora))
        self.assertEqual(db.limpar_reservas_vencidas(ttl=600), 2)
        self.assertTrue(db.esta_reservada("shopee:1", ttl=600))
        self.assertFalse(db.esta_reservada("shopee:2", ttl=600))
        self.assertFalse(db.esta_reservada("shopee:3", ttl=600))


# ─────────────────────────────────────────────────────────────────────
# 2. filtrar() reserva — a segunda chamada não recebe nada
# ─────────────────────────────────────────────────────────────────────

class TestFiltrarReserva(BancoTemporario):
    def setUp(self):
        super().setUp()
        self.patches = [
            patch.object(pipeline, "passes_product_filters",
                         return_value=(True, "")),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])

    def test_oferta_aprovada_sai_reservada(self):
        o = oferta_de_teste(id_produto="1")
        aprovadas = pipeline.filtrar([o])
        self.assertEqual(len(aprovadas), 1)
        self.assertTrue(db.esta_reservada(o.uid),
                        "filtrar tem de reservar: sem isso a corrida volta")

    def test_a_segunda_chamada_nao_recebe_a_mesma_oferta(self):
        """É aqui que morria o post repetido: dois processos, uma oferta."""
        o = oferta_de_teste(id_produto="1")
        self.assertEqual(len(pipeline.filtrar([o])), 1, "a primeira leva")
        self.assertEqual(pipeline.filtrar([o]), [],
                         "a segunda não pode levar a mesma oferta")

    def test_oferta_ja_postada_nao_e_reservada(self):
        o = oferta_de_teste(id_produto="1")
        db.registrar(o)
        self.assertEqual(pipeline.filtrar([o]), [])
        self.assertFalse(db.esta_reservada(o.uid))

    def test_rejeitada_pelos_filtros_nao_reserva(self):
        with patch.object(pipeline, "passes_product_filters", return_value=(False, "sem vendas")):
            o = oferta_de_teste(id_produto="1")
            self.assertEqual(pipeline.filtrar([o]), [])
        self.assertFalse(db.esta_reservada(o.uid),
                         "reservar uma oferta que nem vai ser tentada trava ela à toa")


# ─────────────────────────────────────────────────────────────────────
# 3. executar_ciclo: quem não publica, devolve a reserva
# ─────────────────────────────────────────────────────────────────────

class TestCicloDevolveReserva(BancoTemporario):
    def setUp(self):
        super().setUp()
        self.publicadas: list[Oferta] = []

        async def postar(bot, oferta, chat_id):
            self.publicadas.append(oferta)

        self.parceiros = [
            patch.object(pipeline, "dentro_do_horario", return_value=True),
            patch.object(pipeline, "postar_oferta", postar),
            patch.object(config, "max_posts_por_ciclo", 3),
            # O ciclo dorme entre postagens; com o valor do config.yaml a suíte
            # levava dois minutos só esperando.
            patch.object(config, "espacamento_segundos", 0),
            # `ativo` é property do GrokService e não tem setter: troca o
            # serviço inteiro em vez de tentar escrever no atributo.
            patch.object(pipeline, "grok_service", MagicMock(ativo=False)),
            patch.object(pipeline, "passes_product_filters",
                         return_value=(True, "")),
            patch.object(pipeline.publishing_controller, "pode_publicar",
                         return_value=(True, "", 0)),
            patch.object(pipeline.publishing_controller, "registrar_publicacao"),
        ]
        for p in self.parceiros:
            p.start()
            self.addCleanup(p.stop)

    def _rodar(self, ofertas: list[Oferta]) -> int:
        with patch.object(pipeline, "coletar", return_value=ofertas):
            return asyncio.run(pipeline.executar_ciclo(MagicMock()))

    def _oferta(self, id_produto, plataforma="shopee") -> Oferta:
        return oferta_de_teste(id_produto=id_produto, plataforma=plataforma,
                               url_afiliado=f"https://exemplo/{id_produto}")

    def test_o_que_sobrou_no_limbo_volta_ao_limbo(self):
        """Se sobrou oferta aprovada e o ciclo só posta poucas, o resto volta."""
        o1, o2, o3 = (self._oferta("1"), self._oferta("2"), self._oferta("3"))
        with patch.object(config, "max_posts_por_ciclo", 1):
            postadas = self._rodar([o1, o2, o3])

        self.assertEqual(postadas, 1)
        self.assertEqual([o.uid for o in self.publicadas], [o1.uid])
        self.assertFalse(db.esta_reservada(o1.uid), "a postada vira registro")
        for o in (o2, o3):
            self.assertFalse(db.esta_reservada(o.uid),
                             f"{o.uid} nem foi tentada; não pode ficar travada")

    def test_sem_link_de_afiliado_volta_ao_limbo(self):
        o = self._oferta("1")
        o.url_afiliado = ""
        self.assertEqual(self._rodar([o]), 0)
        self.assertFalse(db.esta_reservada(o.uid))

    def test_oferta_ignorada_pelo_grok_volta_ao_limbo(self):
        o = self._oferta("1")
        o.tipo = "irrelevante"
        self.assertEqual(self._rodar([o]), 0)
        self.assertFalse(db.esta_reservada(o.uid))

    def test_falha_no_envio_volta_ao_limbo(self):
        o = self._oferta("1")

        async def postar_quebrado(bot, oferta, chat_id):
            raise RuntimeError("telegram fora do ar")

        with patch.object(pipeline, "postar_oferta", postar_quebrado):
            postadas = self._rodar([o])

        self.assertEqual(postadas, 0)
        self.assertFalse(db.esta_reservada(o.uid), "falha de envio não pode travar a oferta")
        self.assertFalse(db.ja_postada(o.uid, 7), "nem registrar o que não foi publicado")

    def test_pausa_no_meio_nao_trava_as_restantes(self):
        """O `break` da pausa deixa as ofertas seguintes intocadas — elas têm de
        voltar ao limbo, senão a pausa vira perda."""
        o1, o2 = self._oferta("1"), self._oferta("2")
        chamadas = {"n": 0}

        def pode_publicar():
            chamadas["n"] += 1
            return (True, "", 0) if chamadas["n"] == 1 else (False, "pausado", 300)

        with patch.object(pipeline.publishing_controller, "pode_publicar", side_effect=pode_publicar):
            postadas = self._rodar([o1, o2])

        self.assertEqual(postadas, 1)
        self.assertFalse(db.esta_reservada(o1.uid))
        self.assertFalse(db.esta_reservada(o2.uid))


# ─────────────────────────────────────────────────────────────────────
# 4. montar_caption: preço absurdo não pode virar texto de anúncio
# ─────────────────────────────────────────────────────────────────────

class TestPrecoNaLegenda(unittest.TestCase):
    def test_preco_negativo_nao_vai_para_a_legenda(self):
        texto = montar_caption(oferta_de_teste(preco=-10.0))
        self.assertNotIn("R$ -10", texto)
        self.assertNotIn("-10,00", texto)

    def test_preco_zero_e_preco_none_sao_tratados_iguais(self):
        for preco in (0, 0.0, None):
            with self.subTest(preco=preco):
                texto = montar_caption(oferta_de_teste(preco=preco))
                self.assertNotIn("Por:", texto)
                self.assertNotIn("De:", texto)

    def test_preco_nao_finito_e_ignorado(self):
        for preco in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(preco=preco):
                texto = montar_caption(oferta_de_teste(preco=preco))
                self.assertNotIn("nan", texto.lower())
                self.assertNotIn("inf", texto.lower())
                self.assertNotIn("Por:", texto)

    def test_desconto_fora_de_1_a_99_nao_vai_para_a_legenda(self):
        """Ruído da página não pode virar selo.

        Quando o site informa um desconto impossível (0, 100, negativo, 250%),
        a legenda recalcula a partir dos dois preços em vez de repetir o número
        quebrado. O selo que aparece tem de ser o de verdade: 50%.
        """
        for desconto in (0, 100, -5, 250):
            with self.subTest(desconto=desconto):
                o = oferta_de_teste(preco=50.0, preco_original=100.0, desconto_pct=desconto)
                texto = montar_caption(o)
                # Compara o número do selo, não a string: "50% OFF" contém
                # "0% OFF" como pedaço e a checagem por substring mentiria.
                self.assertEqual(re.findall(r"(\d+)% OFF", texto), ["50"])

    def test_centavos_viram_por_extenso(self):
        """419,00 truncado para 419 era o defeito: a pessoa prometia R$ 419,00
        e o produto custava R$ 419,90."""
        o = oferta_de_teste(preco=419.90, preco_original=499.90)
        texto = montar_caption(o)
        self.assertIn("419,90", texto)
        self.assertNotIn("419,00", texto)

    def test_sem_preco_anterior_nao_inventa_de_por(self):
        texto = montar_caption(oferta_de_teste(preco=49.90, preco_original=None))
        self.assertIn("49,90", texto)
        self.assertNotIn("De:", texto)
        self.assertNotIn("OFF", texto)

    def test_preco_anterior_menor_que_o_atual_nao_inventa_desconto(self):
        texto = montar_caption(oferta_de_teste(preco=100.0, preco_original=80.0))
        self.assertNotIn("De:", texto)
        self.assertNotIn("OFF", texto)

    def test_desconto_calculado_quando_o_site_nao_informa(self):
        o = oferta_de_teste(preco=50.0, preco_original=100.0, desconto_pct=None)
        self.assertIn("50% OFF", montar_caption(o))


# ─────────────────────────────────────────────────────────────────────
# 5. Leitor de preço do ML, contra HTML de verdade
# ─────────────────────────────────────────────────────────────────────

class TestLeitorDePrecoMl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(FIXTURE_PRECOS, encoding="utf-8") as f:
            cls.dados = json.load(f)

    def test_tem_produtos_capturados(self):
        self.assertGreaterEqual(len(self.dados["produtos"]), 4)

    def test_preco_esperado_e_lido_do_html_real(self):
        for produto in self.dados["produtos"]:
            with self.subTest(url=produto["url"][-30:]):
                soup = BeautifulSoup(produto["html"], "lxml")
                atual, anterior = mercadolivre._precos_da_pagina(soup)
                self.assertIsNotNone(atual, "não leu preço nenhum")
                self.assertAlmostEqual(
                    atual, produto["preco_esperado"], places=2,
                    msg=f"preço lido {atual} != {produto['preco_esperado']}",
                )
                if produto.get("anterior_esperado") is not None:
                    self.assertAlmostEqual(anterior, produto["anterior_esperado"], places=2)

    def test_le_o_centavo_e_nao_so_a_fracao(self):
        """A parte de centavos (`__cents`) é o que distingue 49,90 de 49,00."""
        html = """
        <div class="ui-pdp-price__second-line">
          <span class="andes-money-amount">
            <span class="andes-money-amount__fraction">49</span>
            <span class="andes-money-amount__cents">90</span>
          </span>
        </div>
        """
        atual, _ = mercadolivre._precos_da_pagina(BeautifulSoup(html, "lxml"))
        self.assertAlmostEqual(atual, 49.90, places=2)

    def test_bloco_inteiro_nao_so_a_fracao(self):
        """Ler só a fração entregava 419 para um produto de R$ 419,90 — e o
        desconto derivado saía errado. O leitor tem de usar reais + centavos."""
        html = """
        <div class="ui-pdp-price__second-line">
          <span class="andes-money-amount">
            <span class="andes-money-amount__fraction">419</span>
            <span class="andes-money-amount__cents">90</span>
          </span>
        </div>
        """
        atual, _ = mercadolivre._precos_da_pagina(BeautifulSoup(html, "lxml"))
        self.assertAlmostEqual(atual, 419.90, places=2)

    def test_preco_anterior_presente_no_html(self):
        html = """
        <meta itemprop="price" content="263.41">
        <s class="andes-money-amount--previous">
          <span class="andes-money-amount__fraction">399</span>
          <span class="andes-money-amount__cents">00</span>
        </s>
        """
        atual, anterior = mercadolivre._precos_da_pagina(BeautifulSoup(html, "lxml"))
        self.assertAlmostEqual(atual, 263.41, places=2)
        self.assertAlmostEqual(anterior, 399.00, places=2,
                               msg="o preço anterior também não pode perder os centavos")

    def test_pagina_sem_preco_devolve_none(self):
        atual, _ = mercadolivre._precos_da_pagina(
            BeautifulSoup("<html><body>Página bloqueada</body></html>", "lxml"))
        self.assertIsNone(atual)

    def test_reler_preco_nao_derruba_quando_a_leitura_falha(self):
        with patch.object(mercadolivre, "sessao") as s:
            s.return_value.get.side_effect = RuntimeError("403 do Mercado Livre")
            self.assertEqual(mercadolivre.reler_preco("https://ml/x"), (None, None))


# ─────────────────────────────────────────────────────────────────────
# 6. Pendentes do ML: a oferta não pode sumir e o preço tem de ser o de hoje
# ─────────────────────────────────────────────────────────────────────

class TestPendentesMl(BancoTemporario):
    def setUp(self):
        super().setUp()
        self.oferta = Oferta(
            plataforma="mercadolivre",
            id_produto="MLB123",
            titulo="Produto pendente do Mercado Livre",
            preco=100.00,
            preco_original=150.00,
            url_produto="https://www.mercadolivre.com.br/x",
            url_afiliado="https://goto/ML123",
        )
        db.salvar_oferta_pendente_ml(self.oferta)
        self.bot = MagicMock()
        # Sem canal de destino o serviço nem tenta postar (e sai antes, com
        # "sem canal de destino ou sem bot"), então o teste não veria nada.
        patch.object(config, "chat_id", -1001234567890).start()
        self.addCleanup(patch.stopall)

    def _pendentes(self) -> list[dict]:
        return db.listar_ofertas_pendentes_ml(status="aguardando_autenticacao")

    def test_falha_no_postar_mantem_a_pendencia(self):
        """Antes, uma falha apagava a pendência e a oferta sumia em silêncio:
        ninguém recebia, ninguém era avisado, e não havia como recuperar."""
        with patch.object(pipeline, "passes_product_filters", return_value=(True, "")), \
             patch.object(ml_auth_service, "gerar_links_afiliado", gerar_links), \
             patch.object(ml_auth_service, "_atualizar_preco"), \
             patch.object(pipeline, "postar_oferta", side_effect=RuntimeError("telegram caiu")):
            publicadas = ml_auth_service.processar_ofertas_pendentes(self.bot)

        self.assertEqual(publicadas, 0)
        self.assertEqual(len(self._pendentes()), 1,
                         "a pendência não pode ser apagada quando o post falha")
        self.assertFalse(db.esta_reservada(self.oferta.uid),
                         "a reserva tem de voltar ao limbo")
        self.assertFalse(db.ja_postada(self.oferta.uid, 7))

    def test_sucesso_remove_a_pendencia_e_registra(self):
        with patch.object(pipeline, "passes_product_filters", return_value=(True, "")), \
             patch.object(ml_auth_service, "gerar_links_afiliado", gerar_links), \
             patch.object(ml_auth_service, "_atualizar_preco"), \
             patch.object(pipeline, "postar_oferta"):
            publicadas = ml_auth_service.processar_ofertas_pendentes(self.bot)

        self.assertEqual(publicadas, 1)
        self.assertEqual(self._pendentes(), [])
        self.assertTrue(db.ja_postada(self.oferta.uid, 7))

    def test_sem_link_de_afiliado_mantem_a_pendencia(self):
        """Link de afiliado é obrigatório (regra do projeto). Se ele não sair,
        a oferta continua na fila — não pode ser descartada."""
        with patch.object(pipeline, "passes_product_filters", return_value=(True, "")), \
             patch.object(ml_auth_service, "gerar_links_afiliado"), \
             patch.object(mercadolivre, "reler_preco", return_value=(59.90, 99.90)), \
             patch.object(pipeline, "postar_oferta") as postar:
            publicadas = ml_auth_service.processar_ofertas_pendentes(self.bot)

        self.assertEqual(publicadas, 0)
        postar.assert_not_called()
        self.assertEqual(len(self._pendentes()), 1)

    def test_o_preco_e_relido_antes_de_publicar(self):
        """O preço foi lido quando a oferta foi coletada; a pendência pode ter
        esperado horas pelo login do ML. O que vai ao ar é o preço de agora."""
        with patch.object(pipeline, "passes_product_filters", return_value=(True, "")), \
             patch.object(ml_auth_service, "gerar_links_afiliado", gerar_links), \
             patch.object(pipeline, "postar_oferta") as postar, \
             patch.object(mercadolivre, "reler_preco", return_value=(59.90, 99.90)) as reler:
            ml_auth_service.processar_ofertas_pendentes(self.bot)

        reler.assert_called_once()
        publicado = postar.call_args[0][1]
        self.assertAlmostEqual(publicado.preco, 59.90, places=2)
        self.assertIn("59,90", montar_caption(publicado),
                      "a mensagem tem de trazer o preço relido, não o guardado")

    def test_se_a_releitura_falha_mantem_o_preco_guardado(self):
        """Falha de leitura pode ser bloqueio do ML, não produto fora do ar.
        Descartar a oferta aqui seria perder uma venda que ainda existe."""
        with patch.object(pipeline, "passes_product_filters", return_value=(True, "")), \
             patch.object(ml_auth_service, "gerar_links_afiliado", gerar_links), \
             patch.object(pipeline, "postar_oferta") as postar, \
             patch.object(mercadolivre, "reler_preco", return_value=(None, None)):
            ml_auth_service.processar_ofertas_pendentes(self.bot)

        publicado = postar.call_args[0][1]
        self.assertAlmostEqual(publicado.preco, 100.00, places=2)

    def test_ja_postada_remove_a_pendencia_sem_postar_de_novo(self):
        db.registrar(self.oferta)
        with patch.object(pipeline, "postar_oferta") as postar, \
             patch.object(mercadolivre, "reler_preco", return_value=(59.90, 99.90)) as reler:
            publicadas = ml_auth_service.processar_ofertas_pendentes(self.bot)

        self.assertEqual(publicadas, 0)
        self.assertEqual(self._pendentes(), [], "pendência já cumprida deve sair")
        postar.assert_not_called()
        reler.assert_not_called()


class TestFiltroExigePreco(unittest.TestCase):
    """O filtro de preco: nenhuma oferta sem preco utilizavel e publicada.

    O caminho que discoveries isto nao foi a lista de ofertas do ciclo (que
    sempre traz preco), e sim o scraper do Telegram: os links curtos da Shopee
    do NERD OFERTAS apontam para produto fora do catalogo de ofertas da Open
    API, `converter` cai no fallback e devolve titulo "Oferta Shopee" com
    preco None. Isso passava por todos os filtros e virava post vazio:

        \U0001F525 <b>Oferta Shopee</b>
        \U0001F9E1 Shopee
    """

    def _oferta(self, **kw) -> Oferta:
        base = dict(plataforma="shopee", id_produto="58255664210",
                    titulo="Oferta Shopee", url_afiliado="https://s.shopee.com.br/abc")
        base.update(kw)
        return Oferta(**base)

    def test_o_caso_real_do_scraper_e_rejeitado(self):
        ok, motivo = passes_product_filters(self._oferta(preco=None))
        self.assertFalse(ok)
        self.assertEqual(motivo, "sem_preco")

    def test_preco_zero_negativo_e_nan(self):
        for valor in (0.0, -10.0, float("nan"), float("inf")):
            with self.subTest(preco=valor):
                ok, motivo = passes_product_filters(self._oferta(preco=valor))
                self.assertFalse(ok)
                self.assertEqual(motivo, "sem_preco")

    def test_preco_ausente(self):
        oferta = self._oferta()
        oferta.preco = None
        self.assertEqual(passes_product_filters(oferta)[1], "sem_preco")

    def test_booleano_nao_vira_preco(self):
        """True e 1 em Python: um parse que devolveu True viraria R$ 1,00."""
        for valor in (True, False):
            with self.subTest(preco=valor):
                self.assertEqual(passes_product_filters(self._oferta(preco=valor))[1],
                                 "sem_preco")

    def test_preco_valido_passa(self):
        for valor in (11.9, 79.99, 1358.00, 1):
            with self.subTest(preco=valor):
                ok, motivo = passes_product_filters(self._oferta(preco=valor, titulo="Furadeira"))
                self.assertTrue(ok, f"preco {valor} foi rejeitado: {motivo}")

    def test_legenda_nao_publica_preco_inventado(self):
        """A legenda jamais deve preencher o buraco com um R$ 0,00."""
        oferta = self._oferta(preco=None)
        legenda = montar_caption(oferta)
        self.assertNotIn("R$ 0", legenda)
        self.assertNotIn("None", legenda)
        self.assertNotIn("nan", legenda.lower())

    def test_o_ciclo_nao_e_afetado(self):
        """As 5 ofertas ja publicadas no ciclo real tem preco e titulo."""
        for preco, titulo in ((11.9, "Pano Microfibra"), (42.89, "Fone de Ouvido"),
                              (4.69, "Raspador de Lingua"), (79.99, "Parafusadeira"),
                              (68.9, "Creatina")):
            with self.subTest(preco=preco):
                ok, motivo = passes_product_filters(
                    self._oferta(preco=preco, titulo=titulo))
                self.assertTrue(ok, motivo)


if __name__ == "__main__":
    unittest.main(verbosity=2)

