"""Testes da fonte Nerd Ofertas (feed público do alerta.nerdofertas.com).

O que precisa estar garantido:
- alerta do canal que é o próprio destino é ignorado (anti-duplicação);
- alerta já processado não é reprocessado nem baixa foto de novo;
- alerta novo entra no pipeline de mensagens com a foto em bytes e com
  (source_id, message_id) do próprio item — é o que faz a dedup funcionar;
- um alerta que explode não derruba os seguintes;
- falha do feed e fonte inativa não derrubam o ciclo.
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from ofertas import db, pipeline  # noqa: E402
from ofertas.config import config  # noqa: E402
from ofertas.sources import nerdofertas  # noqa: E402

CFG = {"ativa": True, "slug": "nerdavisosbot", "ignorar_canais": ["nerdofertas"], "dry_run": False}


def _item(item_id: int, link: str = "https://t.me/outrocanal/900", **extra) -> dict:
    return {
        "id": item_id,
        "text": "Fone Bluetooth\n✅ R$ 99\nhttps://www.amazon.com.br/dp/B0TESTE",
        "entities": [],
        "photo": "/media/9/123",
        "link": link,
        "source": "Canal de teste",
        "createdAt": 1790731844000,
        **extra,
    }


class TestLeituraDoAlerta(unittest.TestCase):
    def test_canal_do_alerta(self):
        self.assertEqual(nerdofertas.canal_do_alerta(_item(1, "https://t.me/nerdofertas/140664")),
                         "nerdofertas")
        self.assertEqual(nerdofertas.canal_do_alerta(_item(1, "t.me/OutroCanal/12")), "outrocanal")
        self.assertEqual(nerdofertas.canal_do_alerta(_item(1, link="")), "")

    def test_e_canal_proprio(self):
        ignorados = {"nerdofertas"}
        for link in ("https://t.me/nerdofertas/140664", "t.me/nerdofertas/1", "https://t.me/NerdOfertas/2"):
            self.assertTrue(nerdofertas.e_canal_proprio(_item(1, link), ignorados), link)
        self.assertFalse(nerdofertas.e_canal_proprio(_item(1, "https://t.me/outrocanal/900"), ignorados))

    def test_url_da_foto(self):
        self.assertEqual(nerdofertas.url_da_foto(_item(1)), "https://alerta.nerdofertas.com/media/9/123")
        self.assertEqual(nerdofertas.url_da_foto(_item(1, photo="https://cdn/x.jpg")), "https://cdn/x.jpg")
        self.assertEqual(nerdofertas.url_da_foto(_item(1, photo="")), "")

    def test_buscar_alertas_filtra_itens_nao_dict(self):
        resp = MagicMock()
        resp.json.return_value = {"items": [{"id": 1}, "lixo", None, {"id": 2}]}
        with patch.object(nerdofertas, "sessao") as sess:
            sess.return_value.get.return_value = resp
            itens = nerdofertas.buscar_alertas()
        self.assertEqual([i["id"] for i in itens], [1, 2])
        sess.return_value.get.assert_called_once()
        self.assertIn("/api/app/nerdavisosbot/offers", sess.return_value.get.call_args[0][0])

    def test_baixar_foto(self):
        resp = MagicMock()
        resp.content = b"\xff\xd8\xff-foto"
        with patch.object(nerdofertas, "sessao") as sess:
            sess.return_value.get.return_value = resp
            self.assertEqual(nerdofertas.baixar_foto("https://x/media/1"), b"\xff\xd8\xff-foto")
        self.assertIsNone(nerdofertas.baixar_foto(""))

        with patch.object(nerdofertas, "sessao") as sess:
            sess.return_value.get.side_effect = RuntimeError("sem rede")
            self.assertIsNone(nerdofertas.baixar_foto("https://x/media/1"))


class TestProcessarAlertas(unittest.TestCase):
    def setUp(self):
        self.p_cfg = patch.object(config, "fonte_nerdofertas", dict(CFG))
        self.p_cfg.start()
        self.addCleanup(self.p_cfg.stop)

    def test_alerta_novo_vai_para_o_pipeline_com_foto_e_ids(self):
        itens = [
            _item(100, "https://t.me/nerdofertas/140664"),          # próprio canal: fora
            _item(200),                                             # já processado: fora
            _item(300),                                             # novo: entra
        ]

        async def _fake(texto, imagem_url=None, source_id=0, message_id=0, bot=None, dry_run=False):
            _fake.Args = dict(texto=texto, imagem_url=imagem_url, source_id=source_id,
                              message_id=message_id, bot=bot, dry_run=dry_run)
            return {"ok": True}

        bot = MagicMock()
        with patch.object(nerdofertas, "buscar_alertas", return_value=itens), \
             patch.object(nerdofertas, "baixar_foto", return_value=b"\xff\xd8\xff-foto") as baixa, \
             patch.object(db, "ja_processada_msg_telegram", side_effect=lambda s, m: m == 200), \
             patch.object(pipeline, "processar_mensagem_telegram", new=_fake):
            resumo = asyncio.run(nerdofertas.processar_alertas(bot))

        self.assertEqual(resumo["vistos"], 3)
        self.assertEqual(resumo["ignorados_proprio"], 1)
        self.assertEqual(resumo["duplicados"], 1)
        self.assertEqual(resumo["processados"], 1)
        self.assertEqual(resumo["postados"], 1)

        # só o alerta novo chegou ao pipeline, com foto e com a chave de dedup
        baixa.assert_called_once_with("https://alerta.nerdofertas.com/media/9/123")
        self.assertEqual(_fake.Args["imagem_url"], b"\xff\xd8\xff-foto")
        self.assertEqual(_fake.Args["source_id"], "nerdofertas:nerdavisosbot")
        self.assertEqual(_fake.Args["message_id"], 300)
        self.assertIs(_fake.Args["bot"], bot)
        self.assertIn("amazon.com.br", _fake.Args["texto"])

    def test_dry_run_vem_do_config(self):
        with patch.object(config, "fonte_nerdofertas", {**CFG, "dry_run": True}), \
             patch.object(nerdofertas, "buscar_alertas", return_value=[_item(400)]), \
             patch.object(nerdofertas, "baixar_foto", return_value=None), \
             patch.object(db, "ja_processada_msg_telegram", return_value=False), \
             patch.object(pipeline, "processar_mensagem_telegram",
                          new=AsyncMock(return_value={"ok": True, "dry_run": True})) as proc:
            resumo = asyncio.run(nerdofertas.processar_alertas(MagicMock()))

        self.assertTrue(proc.call_args.kwargs["dry_run"])
        self.assertEqual(resumo["processados"], 1)
        self.assertEqual(resumo["postados"], 0)   # dry-run não é postagem

    def test_fonte_inativa_nao_busca(self):
        with patch.object(config, "fonte_nerdofertas", {**CFG, "ativa": False}), \
             patch.object(nerdofertas, "buscar_alertas") as busca:
            resumo = asyncio.run(nerdofertas.processar_alertas(MagicMock()))
        busca.assert_not_called()
        self.assertFalse(resumo["ativo"])
        self.assertTrue(resumo["ok"])

    def test_falha_no_feed_nao_derruba(self):
        with patch.object(nerdofertas, "buscar_alertas", side_effect=RuntimeError("502")):
            resumo = asyncio.run(nerdofertas.processar_alertas(MagicMock()))
        self.assertFalse(resumo["ok"])
        self.assertIn("502", resumo["erro"])

    def test_alerta_que_explode_nao_para_os_outros(self):
        itens = [_item(500), _item(600)]

        async def _fake(texto, imagem_url=None, source_id=0, message_id=0, bot=None, dry_run=False):
            if message_id == 500:
                raise RuntimeError("conversor morreu")
            return {"ok": True}

        with patch.object(nerdofertas, "buscar_alertas", return_value=itens), \
             patch.object(nerdofertas, "baixar_foto", return_value=None), \
             patch.object(db, "ja_processada_msg_telegram", return_value=False), \
             patch.object(pipeline, "processar_mensagem_telegram", new=_fake):
            resumo = asyncio.run(nerdofertas.processar_alertas(MagicMock()))

        self.assertTrue(resumo["ok"])
        self.assertEqual(resumo["processados"], 1)
        self.assertEqual(resumo["postados"], 1)
        # o que exploda fica registrado como "erro" e o resto segue normal
        self.assertEqual(resumo["motivos"], {"erro": 1, "ok": 1})


if __name__ == "__main__":
    unittest.main()