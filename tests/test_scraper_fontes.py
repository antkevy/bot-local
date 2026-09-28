"""O scraper de outros grupos estava desligado — e tinha duas falhas silenciosas.

A causa bloqueante era simples: `data/telethon_session.session` não existe, e
`iniciar_userbot` desiste nessa linha. As credenciais estavam no .env, a fonte
"Nerd Ofertas" estava cadastrada e ativa, e mesmo assim nada nunca foi
capturado — `mensagens_telegram` só tinha a linha que os testes gravavam no
banco de verdade.

Isso aqui trava as duas falhas que teriam mordido assim que o login fosse
feito, porque nenhuma das duas.erraria: as duas simplesmente deixavam a
mensagem passar sem registro nenhum.
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from ofertas import db
from ofertas.sources import telegram_userbot as ub
from ofertas.sources.telegram_scraper import e_postagem_propria


class BancoTemporario(unittest.TestCase):
    def setUp(self):
        self.banco_anterior = db.DB_PATH
        db.DB_PATH = Path(tempfile.mkdtemp(prefix="teste_fonte_")) / "ofertas.db"
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.banco_anterior


class TestChaveDaFonte(BancoTemporario):
    """`_chave_cadastrada` decide se a mensagem entra, e com que chave."""

    def test_encontra_por_username(self):
        db.salvar_fonte_telegram("@nerdofertas", "Nerd Ofertas")
        self.assertEqual(ub._chave_cadastrada("-1001755551234", "@nerdofertas"),
                         "@nerdofertas")

    def test_encontra_por_id_completo(self):
        db.salvar_fonte_telegram("-1001755551234", "Nerd Ofertas")
        self.assertEqual(ub._chave_cadastrada("-1001755551234", "@nerdofertas"),
                         "-1001755551234")

    def test_encontra_por_id_curto(self):
        """Regressão do `lstrip("-100")`.

        `lstrip` remove o conjunto de caracteres {'-', '1', '0'} da esquerda,
        não o prefixo: "-1001234567890" virava "234567890". A fonte era
        encontrada por @username por sorte, e quem cadastrasse pelo id curto
        ficava sem nenhuma mensagem capturada e sem registro do motivo.
        """
        db.salvar_fonte_telegram("1755551234", "Nerd Ofertas")
        self.assertEqual(ub._chave_cadastrada("-1001755551234", "@nerdofertas"),
                         "1755551234")

    def test_nao_confunde_fonte_de_outro_grupo(self):
        db.salvar_fonte_telegram("@outrogrupo", "Outro")
        self.assertIsNone(ub._chave_cadastrada("-1001755551234", "@nerdofertas"))

    def test_id_curto_nao_casa_por_coincidencia_de_digitos(self):
        """O trimming tem de tirar só o prefixo, não o que vier antes dele."""
        db.salvar_fonte_telegram("175551234", "Fonte esquisita")
        self.assertIsNone(
            ub._chave_cadastrada("-1001755551234", ""),
            "o id curto da fonte esquisita não é o mesmo grupo",
        )

    def test_fonte_desligada_nao_captura(self):
        db.salvar_fonte_telegram("@nerdofertas", "Nerd Ofertas", ativa=True)
        db.atualizar_status_fonte_telegram("@nerdofertas", False)
        self.assertIsNone(ub._chave_cadastrada("-1001755551234", "@nerdofertas"))


class TestMarcaUltimaMensagem(BancoTemporario):
    """`ultima_msg_id` precisa andar — é o que a tela do painel mostra."""

    def _fonte(self) -> dict:
        return db.listar_fontes_telegram()[0]

    def test_marca_pelo_username_cadastrado(self):
        db.salvar_fonte_telegram("@nerdofertas", "Nerd Ofertas")
        db.marcar_ultima_mensagem_fonte("@nerdofertas", 4242)
        f = self._fonte()
        self.assertEqual(f["ultima_msg_id"], 4242)
        self.assertIsNotNone(f["ultimo_processamento"])

    def test_registrar_mensagem_tambem_marca(self):
        db.salvar_fonte_telegram("@nerdofertas", "Nerd Ofertas")
        db.registrar_msg_telegram("@nerdofertas", 77, "shopee:1", "ok")
        self.assertEqual(self._fonte()["ultima_msg_id"], 77)

    def test_id_numerico_resolvido_nao_deixa_a_fonte_parada(self):
        """A falha original: o UPDATE usava o id resolvido do Telegram e a
        linha estava cadastrada como @username, então nenhuma linha era
        atualizada e a tela mostrava a data de cadastro para sempre."""
        db.salvar_fonte_telegram("@nerdofertas", "Nerd Ofertas")
        chave = ub._chave_cadastrada("-1001755551234", "@nerdofertas")
        db.registrar_msg_telegram(chave, 99, "shopee:1", "ok")
        self.assertEqual(self._fonte()["ultima_msg_id"], 99,
                         "o '@nerdofertas' cadastrado não foi atualizado")

    def test_mensagem_antiga_nao_regressa_o_marcador(self):
        db.salvar_fonte_telegram("@nerdofertas", "Nerd Ofertas")
        db.marcar_ultima_mensagem_fonte("@nerdofertas", 500)
        db.marcar_ultima_mensagem_fonte("@nerdofertas", 100)
        self.assertEqual(self._fonte()["ultima_msg_id"], 500)

    def test_marcar_nao_mexe_na_flag_ativa(self):
        """Regressão da chamada com argumento trocado: o userbot passava o id
        da mensagem onde a função esperava um booleano, então 'ativa' recebia
        o id e uma fonte desligada pelo dono podia ser reativada sozinha."""
        db.salvar_fonte_telegram("@nerdofertas", "Nerd Ofertas")
        db.atualizar_status_fonte_telegram("@nerdofertas", False)
        db.marcar_ultima_mensagem_fonte("@nerdofertas", 12345)
        self.assertEqual(self._fonte()["ativa"], 0,
                         "marcar mensagem não pode reativar a fonte")


class TestSessaoDoUserbot(unittest.TestCase):
    """A causa bloqueante: sem sessão, o monitor nem sobe."""

    def setUp(self):
        self.patches = [
            patch.object(ub, "tem_credenciais", return_value=True),
            patch.object(ub, "tem_sessao_salva", return_value=False),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_sem_sessao_o_monitor_desiste(self):
        import asyncio
        self.assertFalse(asyncio.run(ub.iniciar_userbot(None)))

    def test_o_painel_conta_o_motivo_da_recusa(self):
        import asyncio
        r = asyncio.run(ub.testar_conexao())
        self.assertFalse(r["ok"])
        self.assertIn("telegram-user-login", r["motivo"],
                      "a recusa precisa dizer o comando que resolve")


class TestStartupDoMonitor(BancoTemporario):
    """O caminho de subida inteiro, com a sessão simulada.

    Este é o teste que teria estragado a festa. `iniciar_userbot` chamava
    `db.listar_fontes_telegram(ativas_apenas=True)`, função que não aceitava o
    argumento: o monitor morria ali, dentro do `except Exception` genérico de
    `bot_interativo._post_init`, que registrava um único aviso
    "Não foi possível iniciar o Telethon Userbot" a cada startup. Um erro de
    código vestido de problema de configuração — e o dono não tinha como
    saber que o login nem era o gargalo.
    """

    def test_com_sessao_o_monitor_sobe(self):
        import asyncio

        db.salvar_fonte_telegram("@nerdofertas", "Nerd Ofertas")

        registrado = {}

        class ClienteFalso:
            def is_connected(self):
                return True

            async def is_user_authorized(self):
                return True

            async def get_me(self):
                return type("Eu", (), {"first_name": "Teste", "username": "teste",
                                       "id": 1})()

            def on(self, evento):
                def deco(fn):
                    registrado["handler"] = fn
                    return fn
                return deco

        with patch.object(ub, "tem_credenciais", return_value=True), \
             patch.object(ub, "tem_sessao_salva", return_value=True), \
             patch.object(ub, "obter_cliente", return_value=ClienteFalso()):
            subiu = asyncio.run(ub.iniciar_userbot(object()))

        self.assertTrue(subiu, "com credenciais e sessão, o monitor tem de subir")
        self.assertIn("handler", registrado, "o handler de mensagens nem foi registrado")

    def test_a_fonte_ativa_e_a_unica_monitorada(self):
        db.salvar_fonte_telegram("@nerdofertas", "Nerd Ofertas")
        db.salvar_fonte_telegram("@desligado", "Desligado", ativa=True)
        db.atualizar_status_fonte_telegram("@desligado", False)
        ativas = db.listar_fontes_telegram(ativas_apenas=True)
        self.assertEqual([f["chat_id"] for f in ativas], ["@nerdofertas"])

    def test_listar_fontes_com_argumento_inexistente_era_o_erro(self):
        """Trava o tipo de erro: função pública chamada com keyword que ela
        não declara. A assinatura virou parte do contrato."""
        with self.assertRaises(TypeError):
            db.listar_fontes_telegram(somente_ativas=True)


class TestAntiLoop(unittest.TestCase):
    """A trava que impede o bot de reprocessar a propria postagem.

    Aqui o `lstrip("-100")` era pior que no `_chave_cadastrada`: o erro nao
    custava uma fonte silenciosa, custava o bot republicando as ofertas que ele
    mesmo acabara de postar, porque a trava deixava de reconhecer o canal de
    destino e o tratava como fonte externa legitima.
    """

    def test_reconhece_o_destino_pelas_tres_formas_de_id(self):
        for origem in ("-1001465877129", "1465877129", -1001465877129):
            with self.subTest(origem=origem):
                self.assertTrue(
                    e_postagem_propria(origem, destination_chat_id="-1001465877129")
                )

    def test_reconhece_o_destino_comecado_em_zero(self):
        """Regressao do lstrip: '-1000123456789' perdia digitos e a trava
        falhava, abrindo caminho para o bot se alimentar do proprio canal."""
        for origem in ("-1000123456789", "0123456789"):
            with self.subTest(origem=origem):
                self.assertTrue(
                    e_postagem_propria(origem, destination_chat_id="-1000123456789"),
                    "o id do destino comeca em 0 e o lstrip comia digitos",
                )

    def test_nao_confunde_outro_canal(self):
        for origem in ("-1003942213987", "3942213987", "@nerdofertas"):
            with self.subTest(origem=origem):
                self.assertFalse(
                    e_postagem_propria(origem, destination_chat_id="-1001465877129")
                )

    def test_canal_de_destino_por_username(self):
        """O destino tambem pode ser cadastrado como @username."""
        self.assertTrue(
            e_postagem_propria("@nerdofertas", destination_chat_id="@nerdofertas")
        )

    def test_sem_destino_configurado_nao_trava(self):
        self.assertFalse(e_postagem_propria("-1001465877129", destination_chat_id=None))

    def test_mensagem_do_proprio_bot(self):
        self.assertTrue(e_postagem_propria(555, bot_id=555, message_from_id=555))
        self.assertFalse(e_postagem_propria(555, bot_id=555, message_from_id=999))


if __name__ == "__main__":
    unittest.main(verbosity=2)
