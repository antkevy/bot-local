"""Login do userbot Telegram a partir do painel — as primitivas sem terminal.

O login do Telethon é interativo (número → código → talvez senha 2FA), então
o painel precisa de uma versão em duas fases, não `client.start()`. O que se
trava aqui:

- `enviar_codigo`/`confirmar_codigo` são as duas fases; elas criam um cliente
  PRÓPRIO (não o `_cliente_global` do monitor) porque se fosse o global, o
  login destrava a conexão que o bot de produção está usando em tempo real.
- o 2FA é um estado, não um erro: o painel pergunta a senha e repete.
- o status fica num arquivo, para o painel mostrar "conectado" SEM abrir a
  sessão — dois Telethon com o mesmo arquivo de sessão brigam pelo DB do
  SQLite e corrompem a sessão do bot.
- `iniciar_userbot` tem de ser idempotente: agora um job de 60s chama ele
  e ele registra o handler de mensagens; registrar duas vezes processaria
  cada oferta em dobro.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# telegram_userbot → pipeline → publishing_control; o import do módulo já
# redireciona db/cadência/cache para um tempdir (ver test_ciclo_pipeline).
import isolamento  # noqa: F401,E402

from ofertas import db  # noqa: E402  (precisa vir antes de config p/ testes)
from ofertas.config import config  # noqa: E402
from ofertas.sources import telegram_userbot as tb  # noqa: E402

try:
    from telethon.errors import FloodWaitError, PasswordHashInvalidError, PhoneCodeInvalidError, SessionPasswordNeededError
except Exception:  # pragma: no cover - telethon e' requisito do projeto
    FloodWaitError = PasswordHashInvalidError = PhoneCodeInvalidError = SessionPasswordNeededError = None


class SentCodeFake:
    def __init__(self, hash_: str = "hash-abc", tipo: str = "auth.sentCodeTypeApp"):
        self.phone_code_hash = hash_
        self.type = type("T", (), {"__class__": type("C", (), {"__name__": tipo.split(".")[-1]})})()


class MeFake:
    def __init__(self, id_=777, primeiro="Ana", username="anaofertas", tel="+5511999998888"):
        self.id = id_
        self.first_name = primeiro
        self.last_name = ""
        self.username = username
        self.phone = tel


class ClienteFake:
    """Fake do TelegramClient com os gatilhos de erro do login real."""

    def __init__(self, session, api_id, api_hash):
        self.session, self.api_id, self.api_hash = session, api_id, api_hash
        self.conectado = False
        self.disconectado = False
        self.codigos: list[str] = []
        self.senhas: list[str] = []
        self.permite_2fa = False
        self.codigo_invalido = False
        self.flood_s = 0

    async def connect(self):
        self.conectado = True

    async def disconnect(self):
        self.disconectado = True

    def is_connected(self):
        return self.conectado

    async def send_code_request(self, telefone: str):
        if self.flood_s:
            raise FloodWaitError(request=None, capture=self.flood_s)
        self.telefone_recebido = telefone
        return SentCodeFake()

    async def sign_in(self, phone=None, code=None, phone_code_hash=None, password=None):
        if password is not None:
            self.senhas.append(password)
            if password != "senha-certa":
                raise PasswordHashInvalidError(request=None)
            self.autorizado = True
            return MeFake()
        self.codigos.append(code)
        if self.permite_2fa:
            raise SessionPasswordNeededError(request=None)
        if self.codigo_invalido or code != "12345":
            raise PhoneCodeInvalidError(request=None)
        self.autorizado = True
        return MeFake()

    async def get_me(self):
        return MeFake()

    async def is_user_authorized(self):
        return getattr(self, "autorizado", False)


class _BaseTeste(unittest.TestCase):
    """Monta um DATA_DIR temporário para não tocar no banco/sessão reais."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.sessao = os.path.join(self._tmp.name, "sessao_teste")
        self._p = [
            patch.object(config, "telegram_api_id", 12345678),
            patch.object(config, "telegram_api_hash", "hash" * 8),
            patch.object(config, "telegram_session", self.sessao),
            patch.object(tb, "ARQUIVO_STATUS", os.path.join(self._tmp.name, "status.json")),
        ]
        for p in self._p:
            p.start()
            self.addCleanup(p.stop)
        tb.ler_status.cache_clear() if hasattr(tb.ler_status, "cache_clear") else None
        # Globais de produção: reset a cada teste para não vazar estado entre
        # eles (o job de 60s de verdade morre junto com o processo).
        tb._monitor_iniciado = False
        tb._cliente_global = None

    def novo_cliente(self, **kw):
        cliente = ClienteFake(self.sessao, 1, "h")
        for k, v in kw.items():
            setattr(cliente, k, v)
        return cliente

    def cliente_instanciado(self, **kw):
        """Devolve um side_effect que sempre entrega um cliente preparado."""
        ultimo = {}

        def _criar(*a, **k):
            c = self.novo_cliente(**kw)
            ultimo["c"] = c
            return c

        _criar.ultimo = ultimo
        return _criar


class TestEnviarCodigo(_BaseTeste):
    def test_enviar_codigo_devolve_o_hash_e_a_forma_de_envio(self):
        criar = self.cliente_instanciado()
        with patch.object(tb, "TelegramClient", side_effect=criar):
            r = asyncio.run(tb.enviar_codigo("+5511999998888"))
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["phone_code_hash"], "hash-abc")
        self.assertEqual(criar.ultimo["c"].telefone_recebido, "+5511999998888")

    def test_enviar_codigo_flood_wait_vira_mensagem_com_segundos(self):
        criar = self.cliente_instanciado(flood_s=33)
        with patch.object(tb, "TelegramClient", side_effect=criar):
            r = asyncio.run(tb.enviar_codigo("+5511999998888"))
        self.assertFalse(r["ok"])
        self.assertIn("33", r["erro"])

    def test_enviar_codigo_telefone_vazio_e_recusado_sem_chamar_a_rede(self):
        criar = self.cliente_instanciado()
        with patch.object(tb, "TelegramClient", side_effect=criar):
            r = asyncio.run(tb.enviar_codigo("   "))
        self.assertFalse(r["ok"])
        self.assertIn("telefone", r["erro"].lower())

    def test_enviar_codigo_desconecta_o_cliente_no_fim(self):
        criar = self.cliente_instanciado()
        with patch.object(tb, "TelegramClient", side_effect=criar):
            asyncio.run(tb.enviar_codigo("+5511999998888"))
        self.assertTrue(criar.ultimo["c"].disconectado)


class TestConfirmarCodigo(_BaseTeste):
    def _confirmar(self, **kw):
        criar = self.cliente_instanciado(**kw)
        with patch.object(tb, "TelegramClient", side_effect=criar):
            r = asyncio.run(tb.confirmar_codigo(
                "+5511999998888", "hash-abc", "12345",
                senha_2fa=kw.pop("senha_2fa", None)))
        return r, criar.ultimo["c"]

    def test_confirmar_com_sucesso_grava_status_conectado(self):
        r, cliente = self._confirmar()
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["user_id"], 777)
        status = tb.ler_status()
        self.assertTrue(status["conectado"])
        self.assertEqual(status["username"], "anaofertas")
        self.assertTrue(cliente.disconectado)

    def test_confirmar_com_2fa_exige_senha(self):
        r, cliente = self._confirmar(permite_2fa=True)
        self.assertFalse(r["ok"])
        self.assertTrue(r.get("precisa_2fa"))
        self.assertNotIn("conectado", tb.ler_status())

    def test_confirmar_com_2fa_e_senha_certa_conecta(self):
        r, _ = self._confirmar(permite_2fa=True, senha_2fa="senha-certa")
        self.assertTrue(r["ok"], r)
        self.assertTrue(tb.ler_status()["conectado"])

    def test_confirmar_com_2fa_e_senha_erra_continua_pedindo(self):
        r, _ = self._confirmar(permite_2fa=True, senha_2fa="errada")
        self.assertFalse(r["ok"])
        self.assertTrue(r.get("precisa_2fa"))

    def test_confirmar_codigo_errado_nao_conecta(self):
        r, _ = self._confirmar(codigo_invalido=True)
        self.assertFalse(r["ok"])
        self.assertNotIn("conectado", tb.ler_status())

    def test_confirmar_sem_credenciais_falha_antes_de_conectar(self):
        with patch.object(config, "telegram_api_id", 0):
            r = asyncio.run(tb.confirmar_codigo("+5511999998888", "h", "12345"))
        self.assertFalse(r["ok"])
        self.assertIn("ausentes", (r["erro"] or "").lower())


class TestArquivoDeStatus(_BaseTeste):
    def test_ler_status_sem_arquivo_devolve_dicionario_vazio(self):
        self.assertEqual(tb.ler_status(), {})

    def test_ler_status_com_arquivo_corrompido_nao_levanta(self):
        with open(tb.ARQUIVO_STATUS, "w", encoding="utf-8") as f:
            f.write("{ quebrado")
        self.assertEqual(tb.ler_status(), {})

    def test_iniciar_userbot_sem_sessao_devolve_falso(self):
        self.assertFalse(os.path.exists(f"{config.telegram_session}.session"))
        r = asyncio.run(tb.iniciar_userbot(bot_poster=None))
        self.assertFalse(r)

    def test_iniciar_userbot_e_idempotente(self):
        """Chamar duas vezes não pode registrar o handler duas vezes."""
        chamadas = []

        def _fingir(cliente, bot, dry):
            chamadas.append(cliente)
            return True

        sessao = f"{config.telegram_session}.session"
        os.makedirs(os.path.dirname(sessao), exist_ok=True)
        with open(sessao, "wb") as f:
            f.write(b"x" * 32)
        self.addCleanup(os.remove, sessao)

        cliente = self.novo_cliente(autorizado=True)
        with patch.object(tb, "TelegramClient", return_value=cliente), \
             patch.object(tb, "tem_credenciais", return_value=True), \
             patch.object(tb, "_iniciar_monitor", side_effect=_fingir):
            asyncio.run(tb.iniciar_userbot(bot_poster=None))
            asyncio.run(tb.iniciar_userbot(bot_poster=None))
        self.assertEqual(len(chamadas), 1)


if __name__ == "__main__":
    unittest.main()
