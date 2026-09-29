"""Nenhum teste pode tocar nos dados de verdade do usuário.

Contexto: `db.py` guardava o caminho do banco numa variável privada `_DB`, mas as
suítes redirecionavam com `db.DB_PATH = <temporário>`. A troca não fazia
nada, e cada execução das três suítes manuais gravava e apagava linhas do
`data/ofertas.db` de verdade — inclusive `DELETE FROM postadas`, que levou o
histórico de postagens a zero. O mesmo valia para o `data/grok_cache.json`, que
o serviço do Grok sobrescrevia a cada otimização de teste.

`db.DB_PATH` passou a ser o nome público (e `_conn()` passa a lê-lo), mas nomes
que não fazem o que promete não tardam a voltar. Este teste existe para falhar
barulhento se isso reaparecer.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from ofertas import db
from ofertas.config import DATA_DIR

# Antes esta lista tinha três nomes. Três de treze: foi o bastante para
# `test_escolha_link.py` e `test_preco_texto.py` passaremimpunes, e entre as
# duas gravaram 12 vezes no `data/cadencia.json` do usuário. A lista agora é
# descoberta, e o arquivo abaixo é a rede: uma suíte nova que esqueça de
# redirecionar quebra aqui em vez de apagar histórico em silêncio.
#
# A si mesma fica de fora, claro: rodar o guard-rail a partir do guard-rail
# seria recursão.
AQUI = Path(__file__).name
SUITES = sorted(
    p.name for p in (RAIZ / "tests").glob("test_*.py")
    if p.name != AQUI
)

# Arquivos de data/ que a execução de um teste jamais pode escrever.
ARQUIVOS_DE_DADOS = ["ofertas.db", "grok_cache.json", "cadencia.json"]


def _dedo(arquivo: Path) -> str:
    """Impressão digital do arquivo: hash do conteúdo, ou 'ausente'."""
    if not arquivo.exists():
        return "ausente"
    return hashlib.sha256(arquivo.read_bytes()).hexdigest()


def _contagens(real: Path) -> dict:
    """Quantas linhas tem cada tabela que importa, no banco real."""
    with sqlite3.connect(real) as c:
        return {
            tabela: c.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
            for tabela in ("postadas", "mensagens_telegram", "ofertas_pendentes_ml")
            if c.execute("SELECT name FROM sqlite_master WHERE name = ?",
                         (tabela,)).fetchone()
        }


class TestRedirecionamentoDoBanco(unittest.TestCase):
    """`db.DB_PATH` precisa ser mesmo o caminho em uso — foi o que não era."""

    def setUp(self):
        self.original = db.DB_PATH

    def tearDown(self):
        db.DB_PATH = self.original

    def test_trocar_db_path_muda_o_arquivo_usado(self):
        temporario = Path(tempfile.mkdtemp()) / "redirecionado.db"
        db.DB_PATH = temporario
        db.init_db()
        self.assertTrue(temporario.exists(), "o banco redirecionado não foi criado")

        with db._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO postadas (uid, plataforma, titulo, preco,"
                " url_afiliado, imagem, postada_em) VALUES"
                " ('x:1', 'x', 't', 1.0, '', '', '2026-01-01T00:00:00')"
            )
        self.assertEqual(db.total_postadas(), 1)

        # E o arquivo original não pode ter ganhado essa linha.
        if self.original.exists():
            with sqlite3.connect(self.original) as c:
                linhas = c.execute(
                    "SELECT COUNT(*) FROM postadas WHERE uid = 'x:1'"
                ).fetchone()[0]
            self.assertEqual(
                linhas, 0,
                "a escrita foi para o banco original: db.DB_PATH não está em uso",
            )

    def test_init_db_cria_todas_as_tabelas(self):
        temporario = Path(tempfile.mkdtemp()) / "novo.db"
        db.DB_PATH = temporario
        db.init_db()
        with db._conn() as c:
            tabelas = {r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        for esperada in ("postadas", "fontes_telegram", "mensagens_telegram",
                         "ofertas_pendentes_ml", "reservas"):
            self.assertIn(esperada, tabelas)


class TestSuitesNaoEncostamNosDadosReais(unittest.TestCase):
    """Roda todas as suítes de verdade e exige que data/ saia intacto."""

    @classmethod
    def setUpClass(cls):
        # As suítes rodam uma vez só. Antes eram dois testes rodando as
        # mesmas três de novo cada um; com treze, isso dobrava o tempo da
        # suíte inteira para produzir a mesma prova.
        real = DATA_DIR / "ofertas.db"
        cls.antes_de = {n: _dedo(DATA_DIR / n) for n in ARQUIVOS_DE_DADOS}
        cls.mtime_antes = {
            n: (DATA_DIR / n).stat().st_mtime_ns
            for n in ARQUIVOS_DE_DADOS if (DATA_DIR / n).exists()
        }
        cls.contagens_antes = _contagens(real) if real.exists() else None

        env = os.environ.copy()
        env["PYTHONPATH"] = str(RAIZ)
        env["PYTHONIOENCODING"] = "utf-8"
        cls.falhas = []
        for nome in SUITES:
            proc = subprocess.run(
                [sys.executable, str(RAIZ / "tests" / nome)],
                cwd=str(RAIZ), env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=600,
            )
            if proc.returncode != 0:
                cls.falhas.append(
                    f"\n=== {nome} terminou com código {proc.returncode} ===\n"
                    f"{(proc.stdout or '')[-2000:]}"
                    f"{(proc.stderr or '')[-2000:]}"
                )
        cls.mtime_depois = {
            n: (DATA_DIR / n).stat().st_mtime_ns
            for n in ARQUIVOS_DE_DADOS if (DATA_DIR / n).exists()
        }
        cls.depois_de = {n: _dedo(DATA_DIR / n) for n in ARQUIVOS_DE_DADOS}
        cls.contagens_depois = _contagens(real) if real.exists() else None

    def test_todas_as_suites_passam(self):
        if self.falhas:
            self.fail("".join(self.falhas))

    def test_nenhuma_suite_altera_a_pasta_data(self):
        sujas = [n for n in ARQUIVOS_DE_DADOS
                 if self.antes_de[n] != self.depois_de[n]]
        self.assertEqual(
            sujas, [],
            f"as suítes alteraram arquivos reais de data/: {sujas}. "
            "Isso apaga histórico do usuário — importe `isolamento` no topo "
            "da suíte, que ele redireciona db.DB_PATH, "
            "ofertas.grok.CACHE_FILE e publishing_control.ARQ_ESTADO.",
        )

    def test_nenhuma_suite_reescreve_arquivo_real(self):
        """Mesmo conteúdo, arquivo reescrito: também é estrago. Reescrever o
        `cadencia.json` do usuário com o estado zerado faz o próximo post
        real passar sem respeitar o intervalo."""
        reescritos = [n for n in self.mtime_antes
                      if self.mtime_depois.get(n) != self.mtime_antes[n]]
        self.assertEqual(
            reescritos, [],
            f"as suítes reescreveram arquivos reais com o mesmo conteúdo: "
            f"{reescritos}",
        )

    def test_o_banco_real_continua_com_as_mesmas_linhas(self):
        """Cintura e suspensório: contam as linhas antes e depois."""
        if self.contagens_antes is None:
            self.skipTest("banco real ainda não existe")
        self.assertEqual(self.contagens_depois, self.contagens_antes,
                         "rodar as suítes alterou o número de linhas do banco real")


if __name__ == "__main__":
    unittest.main(verbosity=2)
