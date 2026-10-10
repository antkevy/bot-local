"""Login do userbot pelas 3 rotas do painel.

O painel guarda telefone+hash de um login EM ANDAMENTO por até LOGIN_TG_TTL
segundos e delega o contato com o Telegram ao telegram_userbot. Ele NUNCA abre
a sessão Telethon: lê/escreve só o ARQUIVO_STATUS (dois clientes com o mesmo
arquivo .session brigam pelo SQLite e corrompem a conexão do bot).

Este teste sobe o painel REAL (ofertas.painel.Handler) num servidor efêmero
em 127.0.0.1, com as credenciais zeradas (→ só loopback, sem sessão) e o
ARQUIVO_STATUS apontando para um tempdir — nada toca o data/ de verdade.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# O painel importa telegram_userbot dentro das rotas → pipeline; isola data/.
import isolamento  # noqa: F401,E402

from ofertas import painel  # noqa: E402
from ofertas.sources import telegram_userbot as tb  # noqa: E402


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        status = os.path.join(self._tmp.name, "userbot.json")
        self._patches = [
            patch.object(tb, "ARQUIVO_STATUS", status),
            patch.object(painel, "_credenciais", return_value=("", "")),
        ]
        for p in self._patches:
            p.start()
        self.addCleanup(self._parar_patches)
        painel._estado_login_tg.clear()

        servidor = ThreadingHTTPServer(("127.0.0.1", 0), painel.Handler)
        self._servidor = servidor
        # poll_interval curto: o shutdown() do serve_forever só repara dele a
        # cada intervalo — com 0.5s padrão cada teste pagava 0.5s de espera.
        self._thread = threading.Thread(
            target=servidor.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self._thread.start()
        self.addCleanup(self._fechar_servidor)
        self.base = f"http://127.0.0.1:{servidor.server_address[1]}"

    def _fechar_servidor(self):
        # shutdown() ANTES de server_close(): fechar o socket com o
        # serve_forever ainda em select provoca WinError 10038 no Windows.
        self._servidor.shutdown()
        self._servidor.server_close()
        self._thread.join(timeout=5)

    def _parar_patches(self):
        for p in self._patches:
            p.stop()

    def get(self, rota: str):
        req = urllib.request.Request(self.base + rota,
                                     headers={"Connection": "close"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))

    def post(self, rota: str, corpo: dict):
        req = urllib.request.Request(
            self.base + rota,
            data=json.dumps(corpo).encode("utf-8"),
            headers={"Content-Type": "application/json", "Connection": "close"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode("utf-8"))
            finally:
                e.close()

    def grava_status(self, **campos):
        with open(tb.ARQUIVO_STATUS, "w", encoding="utf-8") as f:
            json.dump(campos, f)


class TestStatus(_Base):
    def test_sem_arquivo_devolve_desconectado(self):
        cod, r = self.get("/api/userbot/status")
        self.assertEqual(cod, 200)
        self.assertFalse(r.get("conectado"))

    def test_devolve_o_conteudo_do_arquivo(self):
        self.grava_status(conectado=True, username="anaofertas")
        cod, r = self.get("/api/userbot/status")
        self.assertEqual(cod, 200)
        self.assertTrue(r["conectado"])
        self.assertEqual(r["username"], "anaofertas")


class TestEnviarCodigo(_Base):
    def test_recusa_telefone_vazio(self):
        cod, r = self.post("/api/userbot/enviar-codigo", {})
        self.assertEqual(cod, 400)
        self.assertIn("telefone", r["erro"].lower())

    def test_delega_ao_telegram_userbot_e_guarda_a_fase(self):
        with patch.object(tb, "enviar_codigo", new=AsyncMock(
                return_value={"ok": True, "phone_code_hash": "h1", "envio": "app"})) as m:
            cod, r = self.post("/api/userbot/enviar-codigo", {"telefone": "+5511999998888"})
        self.assertEqual(cod, 200)
        self.assertTrue(r["ok"])
        m.assert_awaited_once_with("+5511999998888")
        st = painel._estado_login_tg
        self.assertEqual(st["telefone"], "+5511999998888")
        self.assertEqual(st["hash"], "h1")

    def test_recusa_novo_login_quando_ja_esta_conectado(self):
        self.grava_status(conectado=True, monitorando=True)
        cod, r = self.post("/api/userbot/enviar-codigo", {"telefone": "+5511999998888"})
        self.assertEqual(cod, 409)
        self.assertIn("conectado", r["erro"].lower())


class TestConfirmar(_Base):
    def test_sem_fase_anterior_falha(self):
        cod, r = self.post("/api/userbot/confirmar", {"codigo": "12345"})
        self.assertEqual(cod, 400)

    def test_confirma_com_o_telefone_e_hash_da_fase(self):
        painel._estado_login_tg.update(
            {"telefone": "+5511999998888", "hash": "h1", "criado": time.time()})
        with patch.object(tb, "confirmar_codigo", new=AsyncMock(
                return_value={"ok": True, "nome": "Ana", "username": "anaofertas"})) as m:
            cod, r = self.post("/api/userbot/confirmar", {"codigo": "12345"})
        self.assertEqual(cod, 200)
        self.assertTrue(r["ok"])
        m.assert_awaited_once_with("+5511999998888", "h1", "12345", senha_2fa=None)
        self.assertEqual(painel._estado_login_tg, {})

    def test_senha_2fa_e_repassada(self):
        painel._estado_login_tg.update(
            {"telefone": "+5511999998888", "hash": "h1", "criado": time.time()})
        with patch.object(tb, "confirmar_codigo", new=AsyncMock(
                return_value={"ok": True, "nome": "Ana"})) as m:
            self.post("/api/userbot/confirmar", {"codigo": "12345", "senha": "segredo"})
        m.assert_awaited_once_with("+5511999998888", "h1", "12345", senha_2fa="segredo")

    def test_fase_expirada_fica_inutilizavel(self):
        painel._estado_login_tg.update(
            {"telefone": "+5511999998888", "hash": "h1", "criado": time.time()})
        with patch.object(painel, "LOGIN_TG_TTL", -1):
            cod, r = self.post("/api/userbot/confirmar", {"codigo": "12345"})
        self.assertEqual(cod, 400)
        self.assertIn("expirada", r["erro"].lower())
        self.assertEqual(painel._estado_login_tg, {})

    def test_precisa_2fa_na_resposta_vira_banco_e_a_fase_fica_de_pe(self):
        painel._estado_login_tg.update(
            {"telefone": "+5511999998888", "hash": "h1", "criado": time.time()})
        with patch.object(tb, "confirmar_codigo", new=AsyncMock(
                return_value={"ok": False, "precisa_2fa": True, "erro": "Senha de verificação incorreta."})):
            cod, r = self.post("/api/userbot/confirmar", {"codigo": "12345", "senha": "errada"})
        self.assertTrue(r.get("precisa_2fa"))
        self.assertEqual(painel._estado_login_tg["telefone"], "+5511999998888")
        # A senha errada NÃO derruba a fase: o usuário pode repetir só a senha.
        with patch.object(tb, "confirmar_codigo", new=AsyncMock(
                return_value={"ok": True, "nome": "Ana"})):
            cod, r = self.post("/api/userbot/confirmar", {"codigo": "12345", "senha": "certa"})
        self.assertTrue(r["ok"])


class TestFaltaDeEpc(_Base):
    """Código errado mantém a fase e devolve a mensagem do Telegram."""

    def test_codigo_errado_devolve_o_erro_e_mantem_a_fase(self):
        painel._estado_login_tg.update(
            {"telefone": "+5511999998888", "hash": "h1", "criado": time.time()})
        with patch.object(tb, "confirmar_codigo", new=AsyncMock(
                return_value={"ok": False, "erro": "Código inválido ou expirado. Peça outro."})):
            cod, r = self.post("/api/userbot/confirmar", {"codigo": "00000"})
        self.assertEqual(cod, 400)
        self.assertEqual(r["erro"], "Código inválido ou expirado. Peça outro.")
        self.assertEqual(painel._estado_login_tg["telefone"], "+5511999998888")


if __name__ == "__main__":
    unittest.main()