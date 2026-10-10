"""O cartão de login do userbot na seção Fontes do painel.

Trava a ESTRUTURA da tela (comportamento JS real fica com test_plataformas_ui,
que precisa de playwright): o cartão existe e vem ANTES do "Adicionar fonte"
(login é pré-condição — sem conta logada não há o que ler), as três rotas
novas estão ligadas, e o polling de status NÃO reapinta os inputs — o bug de
"polling apaga o que você digitou" já aconteceu neste painel.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestPainelUserbot(unittest.TestCase):
    def setUp(self):
        from ofertas.painel_html import PAGINA
        self.pagina = PAGINA

    # ── O cartão existe e está na seção certa ────────────────────────

    def test_cartao_existe_dentro_de_sec_fontes_antes_de_adicionar_fonte(self):
        """O login é pré-condição do scraping: vem antes do card de adicionar."""
        sec = self.pagina.index('id="sec-fontes"')
        card = self.pagina.index('id="cardUserbotTelegram"')
        nova = self.pagina.index('id="cardNovaFonteTelegram"')
        self.assertLess(sec, card)
        self.assertLess(card, nova)

    def test_selo_de_status_e_areas_de_aviso_existem(self):
        self.assertIn('id="userbotSelo"', self.pagina)
        self.assertIn('id="userbotAviso"', self.pagina)
        self.assertIn('id="userbotAviso2"', self.pagina)
        self.assertIn('id="userbotConta"', self.pagina)

    # ── Campos e formulários ─────────────────────────────────────────

    def test_campos_de_telefone_codigo_e_senha_existem(self):
        self.assertIn('id="userbotTelefone"', self.pagina)
        self.assertIn('id="userbotCodigo"', self.pagina)
        self.assertIn('id="userbotSenha"', self.pagina)

    def test_form_de_codigo_comeca_escondido(self):
        linha = self._linha('id="formUserbotCodigo"')
        self.assertIn("hidden", linha)

    def test_forms_ligados_aos_handlers(self):
        self.assertIn('onsubmit="userbotEnviarCodigo(event)"', self.pagina)
        self.assertIn('onsubmit="userbotConfirmar(event)"', self.pagina)

    # ── Rotas e polling ──────────────────────────────────────────────

    def test_rodadas_das_tres_rotas(self):
        self.assertIn('fetch("/api/userbot/status"', self.pagina)
        self.assertIn('fetch("/api/userbot/enviar-codigo"', self.pagina)
        self.assertIn('fetch("/api/userbot/confirmar"', self.pagina)

    def test_carregar_userbot_roda_no_inicio_e_e_polled(self):
        self.assertIn("carregarUserbot();", self.pagina)
        self.assertIn("setInterval(carregarUserbot,", self.pagina)

    # ── O polling não pode apagar a digitação ────────────────────────

    def test_polling_de_status_nao_toca_nos_inputs(self):
        corpo = self._corpo("async function carregarUserbot()",
                            "async function userbotEnviarCodigo")
        self.assertNotIn(".value", corpo)

    # ── Valores vindos do Telegram nunca viram HTML cru ─────────────

    def test_dados_da_conta_entram_por_texto_ou_escape(self):
        corpo = self._corpo("async function carregarUserbot()",
                            "async function userbotEnviarCodigo")
        self.assertIn("textContent", corpo)
        self.assertNotIn("${d.nome", corpo)
        self.assertNotIn("${d.username", corpo)

    def _corpo(self, inicio: str, fim: str) -> str:
        i = self.pagina.index(inicio)
        j = self.pagina.index(fim, i)
        return self.pagina[i:j]

    def _linha(self, trecho: str) -> str:
        i = self.pagina.index(trecho)
        ini = self.pagina.rfind("\n", 0, i) + 1
        fim = self.pagina.index("\n", i)
        return self.pagina[ini:fim]


if __name__ == "__main__":
    unittest.main()