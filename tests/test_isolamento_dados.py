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

SUITES = ["test_grok.py", "test_ml_cascata.py", "test_telegram_scraper.py"]

# Arquivos de data/ que a execução de um teste jamais pode escrever.
ARQUIVOS_DE_DADOS = ["ofertas.db", "grok_cache.json", "cadencia.json"]


def _dedo(arquivo: Path) -> str:
    """Impressão digital do arquivo: hash do conteúdo, ou 'ausente'."""
    if not arquivo.exists():
        return "ausente"
    return hashlib.sha256(arquivo.read_bytes()).hexdigest()


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
    """Roda as três suítes de verdade e exige que data/ saia intacto."""

    def test_nenhuma_suite_altera_a_pasta_data(self):
        antes = {nome: _dedo(DATA_DIR / nome) for nome in ARQUIVOS_DE_DADOS}
        modificacao_antes = {
            nome: (DATA_DIR / nome).stat().st_mtime_ns
            for nome in ARQUIVOS_DE_DADOS if (DATA_DIR / nome).exists()
        }

        env = os.environ.copy()
        env["PYTHONPATH"] = str(RAIZ)
        env["PYTHONIOENCODING"] = "utf-8"
        for nome in SUITES:
            with self.subTest(suite=nome):
                proc = subprocess.run(
                    [sys.executable, str(RAIZ / "tests" / nome)],
                    cwd=str(RAIZ), env=env, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=600,
                )
                self.assertEqual(
                    proc.returncode, 0,
                    f"{nome} falhou:\n{(proc.stdout or '')[-2000:]}"
                    f"{(proc.stderr or '')[-2000:]}",
                )

        depois = {nome: _dedo(DATA_DIR / nome) for nome in ARQUIVOS_DE_DADOS}
        sujas = [n for n in ARQUIVOS_DE_DADOS if antes[n] != depois[n]]
        self.assertEqual(
            sujas, [],
            f"as suítes alteraram arquivos reais de data/: {sujas}. "
            "Isso apaga histórico do usuário — confira o redirecionamento de "
            "db.DB_PATH e de ofertas.grok.CACHE_FILE nos scripts de teste.",
        )

        modificacao_depois = {
            nome: (DATA_DIR / nome).stat().st_mtime_ns
            for nome in ARQUIVOS_DE_DADOS if (DATA_DIR / nome).exists()
        }
        reescritos = [n for n in modificacao_antes
                      if modificacao_depois.get(n) != modificacao_antes[n]]
        self.assertEqual(
            reescritos, [],
            f"as suítes reescreveram arquivos reais com o mesmo conteúdo: {reescritos}",
        )

    def test_o_banco_real_continua_com_as_mesmas_linhas(self):
        """Cintura e suspensório: contam as linhas antes e depois."""
        real = DATA_DIR / "ofertas.db"
        if not real.exists():
            self.skipTest("banco real ainda não existe")

        def contagens():
            with sqlite3.connect(real) as c:
                return {
                    tabela: c.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
                    for tabela in ("postadas", "mensagens_telegram",
                                   "ofertas_pendentes_ml")
                    if c.execute(
                        "SELECT name FROM sqlite_master WHERE name = ?",
                        (tabela,)).fetchone()
                }

        antes = contagens()
        env = os.environ.copy()
        env["PYTHONPATH"] = str(RAIZ)
        env["PYTHONIOENCODING"] = "utf-8"
        for nome in SUITES:
            subprocess.run(
                [sys.executable, str(RAIZ / "tests" / nome)],
                cwd=str(RAIZ), env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=600,
            )
        self.assertEqual(contagens(), antes,
                         "rodar as suítes alterou o número de linhas do banco real")


if __name__ == "__main__":
    unittest.main(verbosity=2)
