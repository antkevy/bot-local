"""O /addfonte valida o formato do chat_id ANTES de gravar.

O chat_id vira valor renderizado no painel e em mensagens do bot; gravar cru
(aspas, tags, espaços) era a porta de entrada do XSS do onclick interpolado.
Aqui: normaliza (id / @username / t.me/...) e só salva formato seguro.
"""
from __future__ import annotations

import asyncio
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ofertas import bot_interativo as bi  # noqa: E402


class MsgFake:
    def __init__(self):
        self.replies: list[str] = []

    async def reply_text(self, texto: str, parse_mode: str | None = None):
        self.replies.append(texto)


class UpdateFake:
    def __init__(self, msg):
        self.message = msg


class CtxArgs:
    def __init__(self, args):
        self.args = args


class TestCmdAddFonte(unittest.TestCase):
    def setUp(self):
        self.msg = MsgFake()
        self.update = UpdateFake(self.msg)

    def rodar(self, args):
        with patch.object(bi, "_e_dono", return_value=True), \
             patch.object(bi.db, "salvar_fonte_telegram") as salva:
            asyncio.run(bi._cmd_add_fonte(self.update, CtxArgs(args)))
        return salva

    def test_rejeita_chat_id_com_aspas_e_tags(self):
        salva = self.rodar(['" onmouseover="alert(1)'])
        salva.assert_not_called()
        self.assertIn("Formato inválido", self.msg.replies[0])

    def test_rejeita_valor_com_espaco(self):
        salva = self.rodar(["canal com espaco"])
        salva.assert_not_called()
        self.assertIn("Formato inválido", self.msg.replies[0])

    def test_aceita_id_numerico_negativo(self):
        salva = self.rodar(["-1001234567890", "Meu canal"])
        salva.assert_called_once_with("-1001234567890", "Meu canal",
                                      tipo="canal", ativa=True)

    def test_aceita_username_e_normaliza_link_tme(self):
        salva = self.rodar(["https://t.me/canal_ofertas"])
        salva.assert_called_once_with("@canal_ofertas", "Canal @canal_ofertas",
                                      tipo="canal", ativa=True)

    def test_sem_argumento_mostra_uso(self):
        salva = self.rodar([])
        salva.assert_not_called()
        self.assertIn("Uso:", self.msg.replies[0])


if __name__ == "__main__":
    unittest.main()