"""Mobile: os ajustes de toque e de layout para tela pequena continuam lá.

O painel nasce desktop e desce pra celular por media queries. Esta passada
adiciona, em blocos próprios DEPOIS dos media queries existentes:
  - viewport-fit=cover (área segura de entalhe);
  - touch-action: manipulation (sem delay de double-tap em celular);
  - alvo de toque de 44px na barra de navegação e nos botões;
  - inputs de 16px (sem zoom do iOS ao focar);
  - modal e gaveta em largura total;
  - tabela mais densa;
  - nav vira barra de abas FIXA no rodapé e o botão de ligar/desligar o
    bot (#botCartao) fica sempre visível no topo.

Estes testes travam a ESTRUTURA da página (o comportamento real de layout
fica com test_plataformas_ui, que precisa de playwright). Cada regra nova é
ancorada no texto exato: se alguém apagar a regra pra "simplificar", o
benefício some no navegador e o teste acusa.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestPainelMobile(unittest.TestCase):
    def setUp(self):
        from ofertas.painel_html import PAGINA
        self.pagina = PAGINA

    def test_viewport_cobre_a_area_segura(self):
        """viewport-fit=cover: conteúdo não fica sob entalhe em landscape."""
        self.assertIn(
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
            self.pagina,
        )

    def test_interativos_sem_delay_de_double_tap(self):
        """touch-action: manipulation vence o double-tap (~300ms) em celular."""
        self.assertIn(
            ':where(a, button, input, select, textarea, [role="button"]) { touch-action: manipulation; }',
            self.pagina,
        )

    def test_alvo_de_toque_da_navegacao(self):
        """Nav de celular (barra de ícones no topo) com alvo >= 44px."""
        self.assertIn(
            ".nav-item { min-width: 44px; min-height: 44px; justify-content: center; }",
            self.pagina,
        )

    def test_inputs_de_16px_evitam_zoom_do_ios(self):
        """Campos de formulário e o link de saída >= 16px (sem zoom ao focar)."""
        self.assertIn(
            ".campo input, .campo select, .saida-link input { font-size: 16px; }",
            self.pagina,
        )

    def test_modal_e_gaveta_em_largura_total(self):
        """Modal acompanha a barra de URL (100dvh) e a gaveta ocupa a tela."""
        self.assertIn(
            ".modal { max-height: calc(100dvh - 20px); border-radius: var(--r-md); }",
            self.pagina,
        )
        self.assertIn(".gaveta { max-width: 100%; }", self.pagina)

    def test_tabela_densa_no_celular(self):
        """Menos padding e letra menor: mais colunas visíveis antes do scroll."""
        self.assertIn(".tabela { font-size: 12px; }", self.pagina)
        self.assertIn(".tabela th, .tabela td { padding: 9px 10px; }", self.pagina)

    def test_botao_do_bot_sempre_visivel_no_topo(self):
        """O #botCartao fica fora do fluxo que rolava pra fora da tela.

        Antes, marca + nav + botão tudo numa linha somavam ~500px: o botão
        de ligar/desligar o bot saía da tela (só via scroll horizontal).
        Agora o topo é só marca + botão, lado a lado, sem scroll.
        """
        self.assertIn(".bot-cartao { flex: none; max-width: 190px; }", self.pagina)
        self.assertIn(
            ".sidebar {\n      justify-content: space-between; gap: 8px; overflow-x: visible;",
            self.pagina,
        )

    def test_abas_em_barra_fixa_no_rodape(self):
        """A nav desce pro rodapé como barra de abas fixa (43x44 de altura)."""
        self.assertIn(
            ".nav-menu {\n      position: fixed; bottom: 0; left: 0; right: 0; z-index: 40;",
            self.pagina,
        )
        self.assertIn(".main-wrapper { padding-bottom: 64px; }", self.pagina)


if __name__ == "__main__":
    unittest.main()