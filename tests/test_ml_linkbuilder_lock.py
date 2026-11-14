"""Garante que duas coletas do Mercado Livre não abrem dois Chromes ao mesmo tempo.

Antes, duas operações concorrentes no mesmo perfil persistente do navegador
travavam no lock do Chrome e ficavam penduradas, elevando o load da VPS.
Com autenticação só por cookie cada coleta usa um contexto temporário, mas o
`_NAVEGADOR_LOCK` continua serializando as aberturas para não disputar sessão.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import types
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

    def __init__(self, vivos: list):
        self._vivos = vivos
        self.pages = []
        self.fechado = False

    def new_page(self):
        pagina = MagicMock()
        pagina.url = "https://www.mercadolivre.com.br/ofertas"
        return pagina

    def close(self):
        self.fechado = True
        if self._vivos:
            self._vivos.pop()


HTML_CARD = """
<html><body>
<div class="poly-card">
  <a class="poly-component__title"
     href="https://www.mercadolivre.com.br/produto/p/MLB1">Produto</a>
  <div class="poly-price__current">
    <span class="andes-money-amount__fraction">59</span>
    <span class="andes-money-amount__cents">90</span>
  </div>
</div>
</body></html>
"""


class TestNavegadorLock(unittest.TestCase):
    def test_duas_coletas_nao_abrem_dois_chromes(self):
        vivos: list = []
        pico: list = []

        def abrir_falso(pw, headless):
            vivos.append(1)
            pico.append(len(vivos))
            time.sleep(0.15)          # simula o custo de abrir o navegador
            pagina = MagicMock()
            pagina.url = "https://www.mercadolivre.com.br/ofertas"
            pagina.goto = MagicMock()
            pagina.wait_for_selector = MagicMock()
            pagina.content = MagicMock(return_value=HTML_CARD)
            ctx = _CtxFalso(vivos)
            ctx.pages = [pagina]
            return ctx

        erros: list = []

        def executar():
            try:
                mercadolivre._coletar_no_navegador(
                    MagicMock(), [("https://www.mercadolivre.com.br/ofertas", "todas")])
            except BaseException as e:  # noqa: BLE001
                erros.append(e)

        with patch.object(mercadolivre, "_abrir_contexto", side_effect=abrir_falso):
            t1 = threading.Thread(target=executar)
            t2 = threading.Thread(target=executar)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        self.assertFalse(erros, f"erros inesperados: {erros}")
        self.assertEqual(max(pico) if pico else 0, 1,
                         "duas coletas abriram o navegador ao mesmo tempo")
        print("✅ LOCK (coletas concorrentes serializadas): OK")


if __name__ == "__main__":
    unittest.main()
