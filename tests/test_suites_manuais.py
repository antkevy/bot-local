"""Traz as três suítes manuais para a suíte automatizada.

tests/test_grok.py, test_ml_cascata.py e test_telegram_scraper.py definem
funções test_* e as chamam num bloco `if __name__ == "__main__"`. Nenhuma delas
é uma unittest.TestCase, então `unittest discover` as ignorava por completo:
o projeto aparentava ter uma suíte de testes, mas 34 dos 48 testes só rodavam
se alguém soubesse executá-los na mão. O pior caso foi o de test_grok.py, que
quebrava no teste 6 por causa de asserções desatualizadas — e isso não era
visível em lugar nenhum.

Aqui cada script roda em um subprocesso próprio, e não é um detalhe: no topo
deles, test_ml_cascata.py e test_telegram_scraper.py fazem

    db.DB_PATH = TEST_DB_PATH          # global, na importação

Se o unittest os importasse na mesma sessão, apontariam o caminho do banco de
todo o processo para um arquivo temporário e os outros testes passariam a ler
e gravar no lugar errado. O subprocesso mantém o isolamento que esses scripts
tinham quando eram executados à mão.
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

SUITES = [
    "test_grok.py",
    "test_ml_cascata.py",
    "test_telegram_scraper.py",
]


class TestSuitesManuais(unittest.TestCase):
    maxDiff = None

    def test_suites_manuais_passam(self):
        falhas = []
        for nome in SUITES:
            with self.subTest(suite=nome):
                env = os.environ.copy()
                env["PYTHONPATH"] = str(RAIZ)
                env["PYTHONIOENCODING"] = "utf-8"
                proc = subprocess.run(
                    [sys.executable, str(RAIZ / "tests" / nome)],
                    cwd=str(RAIZ), env=env, capture_output=True,
                    text=True, encoding="utf-8", errors="replace", timeout=300,
                )
                if proc.returncode != 0:
                    # Mostra o fim da saída: é onde a asserção que falhou aparece.
                    cauda = (proc.stdout or "")[-2500:]
                    if not cauda.strip():
                        cauda = (proc.stderr or "")[-2500:]
                    falhas.append(
                        f"\n=== {nome} terminou com código {proc.returncode} ===\n"
                        f"{cauda}"
                    )
        if falhas:
            self.fail(
                "".join(falhas)
                + "\n\nCada script também roda direto: "
                  "python tests/test_grok.py"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
