"""Garante que duas gerações de link em paralelo NÃO abrem dois Chromes no
mesmo perfil persistente do Link Builder.

Era a origem do vazamento: dois `launch_persistent_context` concorrentes no
mesmo `data/ml_profile` travavam no lock de perfil do Chrome e ficavam
pendurados; cada mensagem nova empilhava mais um chrome-headless até elevar o
load da VPS a ~37. O `_LINKBUILDER_LOCK` serializa as gerações.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from ofertas.models import Oferta
from ofertas.sources import mercadolivre


class _CtxFalso:
    """Contexto de navegador falso; registra quantos estão abertos ao mesmo tempo."""

    pages: list = []

    def __init__(self, vivos: list):
        self._vivos = vivos

    def new_page(self):
        pagina = MagicMock()
        pagina.url = "https://www.mercadolivre.com.br/afiliados/linkbuilder"
        return pagina

    def close(self):
        self._vivos.pop()


class TestLinkBuilderLock(unittest.TestCase):
    def test_duas_geracoes_nao_abrem_dois_chromes(self):
        ofertas = [
            Oferta(plataforma="mercadolivre", id_produto=f"MLB{i}",
                   url_produto=f"https://www.mercadolivre.com.br/p/MLB{i}", titulo="t")
            for i in range(2)
        ]

        vivos: list = []
        pico: list = []

        def abrir_falso(pw, headless):
            vivos.append(1)
            pico.append(len(vivos))
            time.sleep(0.15)          # simula o custo de abrir o navegador
            return _CtxFalso(vivos)

        def criar_falso(page, urls, etiqueta):
            return [f"https://meli.la/{u[-4:]}" for u in urls]

        erros: list = []

        def executar(oferta):
            try:
                mercadolivre._gerar_links_linkbuilder_batch([oferta], "fastpromo")
            except BaseException as e:  # noqa: BLE001
                erros.append(e)

        # `_gerar_links_linkbuilder_batch` faz `from playwright.sync_api import
        # sync_playwright` internamente; injetamos um módulo falso para o teste
        # não depender do Playwright instalado (só do lock).
        import types
        fake_sync = types.ModuleType("playwright.sync_api")
        fake_sync.sync_playwright = MagicMock()

        with patch.dict(sys.modules, {"playwright": types.ModuleType("playwright"),
                                      "playwright.sync_api": fake_sync}), \
             patch.object(mercadolivre, "_abrir_contexto", side_effect=abrir_falso), \
             patch.object(mercadolivre, "tem_sessao", return_value=True), \
             patch.object(mercadolivre, "_criar_links_api", side_effect=criar_falso):

            t1 = threading.Thread(target=executar, args=(ofertas[0],))
            t2 = threading.Thread(target=executar, args=(ofertas[1],))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        self.assertFalse(erros, f"erros inesperados: {erros}")
        self.assertEqual(
            max(pico), 1,
            "duas gerações abriram o perfil ao mesmo tempo (deadlock do Chrome)")
        for o in ofertas:
            self.assertTrue(o.url_afiliado)
        print("✅ LOCK (gerações concorrentes serializadas): OK")


if __name__ == "__main__":
    unittest.main()
