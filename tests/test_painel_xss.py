"""XSS do painel: valor vindo do banco NUNCA vira código JS.

O chat_id de uma fonte vem de fora (comando /addfonte, formulário do painel) e
antes era interpolado em onclick="testarConexaoFonteItem('${esc(id)}')". O esc()
de HTML não protege nada nesse ponto: as aspas escapadas voltam a viver na
string JS, então um id com aspa virava execução de código.

O fix: o valor só aparece em data-* (atributo escapado) e os botões se
identificam por data-fonte-acao num listener delegado na tabela. Estes testes
travam a ESTRUTURA da página (checagem real de comportamento JS fica com
test_plataformas_ui, que precisa de playwright).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestPainelSemXss(unittest.TestCase):
    def setUp(self):
        from ofertas.painel_html import PAGINA
        self.pagina = PAGINA

    def test_nenhum_onclick_interpola_chat_id(self):
        """Nenhum botão de fonte embute o valor do banco em string de código."""
        self.assertNotIn("onclick=\"testarConexaoFonteItem('", self.pagina)
        self.assertNotIn("onclick=\"alternarStatusFonteTelegram('", self.pagina)
        self.assertNotIn("onclick=\"removerFonteTelegram('", self.pagina)

    def test_valor_da_fonte_so_existe_como_atributo_escapado(self):
        """Os três botões carregam o chat_id em data-*, nunca como argumento de onclick."""
        self.assertIn('data-fonte-acao="testar" data-fonte-chat="${esc(chatId)}" '
                      'title="Testar acesso"', self.pagina)
        self.assertIn('data-fonte-acao="alternar" data-fonte-chat="${esc(chatId)}" '
                      'data-fonte-ativo="${ativo}"', self.pagina)
        self.assertIn('data-fonte-acao="remover" data-fonte-chat="${esc(chatId)}"',
                      self.pagina)

    def test_listener_delegado_registrado_na_tabela(self):
        """O clique nasce como evento na tabela; o botão só carrega dados."""
        self.assertIn('$("#tabelaFontesTelegramCorpo")?.addEventListener("click", ev => {',
                      self.pagina)


if __name__ == "__main__":
    unittest.main()