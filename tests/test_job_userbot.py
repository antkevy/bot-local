"""Auto-ativação do userbot: o job de prontidão do bot_interativo.

O login acontece pelo painel (sem SSH). Entre a sessão aparecer e o monitor
subir não podem ser necessários comandos de terminal: o job checa a cada 60s,
sobe o monitor quando a sessão existe e se cancela sozinho depois. Sem o job,
um login bem-sucedido ficaria órfão até um restart manual.
"""
from __future__ import annotations

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# bot_interativo → pipeline → publishing_control: redireciona o data/ real.
import isolamento  # noqa: F401,E402

from ofertas import bot_interativo as bi  # noqa: E402
from ofertas.sources import telegram_userbot as tb  # noqa: E402

NOME_JOB = "userbot_ativacao"


class JobFake:
    def __init__(self, nome=NOME_JOB):
        self.name = nome
        self.removido = False

    def schedule_removal(self):
        self.removido = True


class JobQueueFake:
    def __init__(self):
        self.jobs = [JobFake()]

    def get_jobs_by_name(self, nome):
        return [j for j in self.jobs if j.name == nome]

    def run_repeating(self, callback, **kwargs):
        self.callback = callback
        self.kwargs = kwargs
        return self.jobs[0]


class AppFake:
    def __init__(self):
        self.job_queue = JobQueueFake()


class CtxFake:
    def __init__(self):
        self.application = AppFake()
        self.job = self.application.job_queue.jobs[0]
        self.bot = object()


class TestJobProntidao(unittest.TestCase):
    def setUp(self):
        self.ctx = CtxFake()
        tb._monitor_iniciado = False

    def run_job(self):
        return asyncio.run(bi._job_userbot(self.ctx))

    def test_sem_sessao_fica_de_prontidao_sem_chamar_o_monitor(self):
        with patch.object(tb, "userbot_ativo", return_value=False), \
             patch.object(tb, "tem_sessao_salva", return_value=False), \
             patch.object(tb, "iniciar_userbot", new=AsyncMock()) as m:
            self.run_job()
        m.assert_not_awaited()
        self.assertFalse(self.ctx.job.removido)

    def test_com_sessao_inicia_o_monitor_e_cancela_o_job(self):
        with patch.object(tb, "userbot_ativo", return_value=False), \
             patch.object(tb, "tem_sessao_salva", return_value=True), \
             patch.object(tb, "iniciar_userbot", new=AsyncMock(return_value=True)) as m:
            self.run_job()
        m.assert_awaited_once()
        self.assertTrue(self.ctx.job.removido)

    def test_sessao_invalida_continua_de_prontidao(self):
        """iniciar_userbot=False (sessão revogada) NÃO cancela: tenta de novo."""
        with patch.object(tb, "userbot_ativo", return_value=False), \
             patch.object(tb, "tem_sessao_salva", return_value=True), \
             patch.object(tb, "iniciar_userbot", new=AsyncMock(return_value=False)) as m:
            self.run_job()
        m.assert_awaited_once()
        self.assertFalse(self.ctx.job.removido)

    def test_monitor_ja_rodando_cancela_sem_tocar_na_sessao(self):
        with patch.object(tb, "userbot_ativo", return_value=True), \
             patch.object(tb, "tem_sessao_salva", return_value=False), \
             patch.object(tb, "iniciar_userbot", new=AsyncMock()) as m:
            self.run_job()
        m.assert_not_awaited()
        self.assertTrue(self.ctx.job.removido)


class TestJobAgendado(unittest.TestCase):
    def test_post_init_agenda_o_job_quando_ha_credenciais(self):
        app = AppFake()
        with patch.object(tb, "tem_credenciais", return_value=True):
            asyncio.run(bi._post_init(app))
        self.assertEqual(app.job_queue.kwargs["name"], NOME_JOB)
        self.assertEqual(app.job_queue.kwargs["interval"], 60)

    def test_post_init_nao_agenda_sem_credenciais(self):
        app = AppFake()
        with patch.object(tb, "tem_credenciais", return_value=False):
            asyncio.run(bi._post_init(app))
        self.assertFalse(hasattr(app.job_queue, "kwargs"))


if __name__ == "__main__":
    unittest.main()