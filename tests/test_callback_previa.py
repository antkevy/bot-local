"""O callback das prévias valida a ação ANTES de consumir o token e não cai em erro.

Regras cobertas aqui:
- ação fora do catálogo (post/drop) não consome o token nem responde como
  descarte — a prévia continua válida;
- post publica no canal e registra; drop descarta sem publicar;
- prévia expirada avisa e não publica;
- falha ao publicar não derruba o handler: o dono vê o erro na prévia.
"""
from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ofertas import bot_interativo as bi  # noqa: E402
from ofertas.bot_interativo import _callback  # noqa: E402
from ofertas.config import config  # noqa: E402
from ofertas.models import Oferta  # noqa: E402


def oferta_x() -> Oferta:
    return Oferta(
        plataforma="shopee",
        id_produto="123",
        titulo="Produto X",
        url_afiliado="https://s.shopee.com.br/x",
        url_produto="https://shopee.com.br/produto-x",
    )


class MsgTexto:
    def __init__(self):
        self.photo = None
        self.text = "Prévia X"
        self.caption = None
        self.editado: list[str] = []

    async def edit_message_text(self, texto: str):
        self.editado.append(texto)

    async def edit_message_caption(self, texto: str):
        self.editado.append(texto)


class MsgFoto:
    def __init__(self):
        self.photo = [1]
        self.caption = "Prévia X"
        self.text = None
        self.editado: list[str] = []

    async def edit_message_caption(self, texto: str):
        self.editado.append(texto)


class QueryFake:
    """Espelha a API do CallbackQuery: edit_message_* ficam NO QUERY,
    que os encaminha para a mensagem (é assim que o lib real faz)."""

    def __init__(self, data, msg):
        self.data = data
        self.message = msg
        self.answered = False

    async def answer(self):
        self.answered = True

    async def edit_message_text(self, texto: str):
        await self.message.edit_message_text(texto)

    async def edit_message_caption(self, texto: str):
        await self.message.edit_message_caption(texto)


class CtxFake:
    def __init__(self):
        self.bot = MagicMock()


class BaseCallback(unittest.TestCase):
    def setUp(self):
        bi._pendentes.clear()
        config.chat_id = "-1001234567890"
        self.ctx = CtxFake()

    def tearDown(self):
        bi._pendentes.clear()

    def rodar(self, query: QueryFake):
        upd = MagicMock()
        upd.callback_query = query
        asyncio.run(_callback(upd, self.ctx))


class TestValidacaoDeAcao(BaseCallback):
    def test_acao_desconhecida_nao_consome_o_token(self):
        token = "abc1"
        bi._pendentes[token] = oferta_x()
        msg = MsgTexto()
        with patch.object(bi, "postar_oferta", new=AsyncMock()) as posta:
            self.rodar(QueryFake("hack:abc1", msg))
        self.assertIn(token, bi._pendentes, "ação desconhecida não pode matar a prévia")
        self.assertIn("Ação não reconhecida", msg.editado[-1])
        posta.assert_not_awaited()

    def test_data_none_nao_quebra(self):
        msg = MsgTexto()
        self.rodar(QueryFake(None, msg))
        self.assertTrue(msg.editado, "data nula entra no guard e reage sem crash")


class TestAcoesValidas(BaseCallback):
    def test_post_publica_e_registra(self):
        token = "abc2"
        bi._pendentes[token] = oferta_x()
        msg = MsgTexto()
        with patch.object(bi, "postar_oferta", new=AsyncMock()) as posta, \
             patch.object(bi.db, "registrar") as reg:
            self.rodar(QueryFake(f"post:{token}", msg))
        posta.assert_awaited_once()
        self.assertEqual(posta.await_args.args[2], config.chat_id)
        reg.assert_called_once()
        self.assertNotIn(token, bi._pendentes)
        self.assertIn("Postada", msg.editado[-1])

    def test_drop_descarta_sem_publicar(self):
        token = "abc3"
        bi._pendentes[token] = oferta_x()
        msg = MsgTexto()
        with patch.object(bi, "postar_oferta", new=AsyncMock()) as posta:
            self.rodar(QueryFake(f"drop:{token}", msg))
        posta.assert_not_awaited()
        self.assertNotIn(token, bi._pendentes)
        self.assertIn("Descartada", msg.editado[-1])

    def test_oferta_expirada_avisa_e_nao_publica(self):
        msg = MsgTexto()
        with patch.object(bi, "postar_oferta", new=AsyncMock()) as posta:
            self.rodar(QueryFake("post:token_sem_previa", msg))
        posta.assert_not_awaited()
        self.assertIn("expirou", msg.editado[-1])

    def test_callback_com_foto_acrescenta_legenda(self):
        token = "abc4"
        bi._pendentes[token] = oferta_x()
        msg = MsgFoto()
        with patch.object(bi, "postar_oferta", new=AsyncMock()):
            self.rodar(QueryFake(f"drop:{token}", msg))
        self.assertIn("Descartada", msg.editado[-1])


class TestRobustez(BaseCallback):
    def test_falha_ao_publicar_nao_derruba_o_handler(self):
        token = "abc5"
        bi._pendentes[token] = oferta_x()
        msg = MsgTexto()
        with patch.object(bi, "postar_oferta",
                          new=AsyncMock(side_effect=RuntimeError("Telegram caiu"))):
            self.rodar(QueryFake(f"post:{token}", msg))  # sem exceção propagada
        self.assertIn("Erro ao processar", msg.editado[-1])
        self.assertNotIn(token, bi._pendentes)


if __name__ == "__main__":
    unittest.main()