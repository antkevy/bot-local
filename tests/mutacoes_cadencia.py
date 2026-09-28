"""Valida os testes da cadência por mutação: cada alteração tem de quebrar
alguma coisa.

O defeito observado em produção foi `posts_periodo` com 11 registros em 19
segundos, tendo `intervalo_entre_posts_segundos = 300`. Teste que passa
porque o código faz a coisa certa não prova que cobre a coisa; aqui cada
mutação reintroduz o defeito de verdade e exige que a suíte reclame.

Cuidado já conhecido desta sessão: mutação que só muda um log é enganosa.
Todas abaixo mexem em fluxo, guarda ou nome de arquivo.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ARQ = Path("ofertas/publishing_control.py")
ORIGINAL = ARQ.read_text(encoding="utf-8")
BACKUP = Path("ofertas/publishing_control.py.bak_mutacao")

MUTACOES = [
    (
        "volta ao bug original: arquivo ilegivel e so um return mudo",
        '        except (OSError, ValueError) as e:',
        '        except (OSError, ValueError) as e:  # mutacao\n            return',
    ),
    (
        "trava some e o estado desconhecido volta a liberar tudo",
        '            if self.cadencia_ilegivel:\n'
        '                return False, "cadencia_ilegivel (arquivo nao legivel)", 300.0\n',
        '',
    ),
    (
        "tipo errado no arquivo deixa de travar",
        '            self._zera()\n            self.cadencia_ilegivel = True\n\n'
        '    def _zera(self) -> None:',
        '            self._zera()\n\n    def _zera(self) -> None:',
    ),
    (
        "temporario volta a ter um nome so, compartilhado entre processos",
        '        tmp = ARQ_ESTADO.with_name(f"{ARQ_ESTADO.stem}.{os.getpid()}.tmp")',
        '        tmp = ARQ_ESTADO.with_suffix(".json.tmp")',
    ),
    (
        "arquivo ausente tambem zera o intervalo ja conhecido",
        '        except FileNotFoundError:\n'
        '            # Primeira execução: ainda não existe histórico, e não postar é\n'
        '            # justamente o certo. Não é estado ilegível.\n'
        '            return',
        '        except FileNotFoundError:\n            self._zera()\n            return',
    ),
    (
        "canario some e a mentira do intervalo passa em silencio",
        '            if anterior and (agora - anterior) < 60:',
        '            if False:',
    ),
    (
        "o passo 5 nunca mais segura o intervalo entre posts",
        '            if decorrido_post < config.intervalo_entre_posts_segundos:',
        '            if decorrido_post < 0:',
    ),
    (
        "reset deixa de limpar a trava de arquivo ilegivel",
        '            self._zera()\n            self.cadencia_ilegivel = False\n            self._salvar()',
        '            self._zera()\n            self._salvar()',
    ),
]


def rodar():
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_cadencia"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, proc.stdout + proc.stderr


def main():
    shutil.copy2(ARQ, BACKUP)
    try:
        base_code, base_out = rodar()
        print(f"[base] codigo={base_code} -> {'PASSOU' if base_code == 0 else 'JA FALHA'}")
        if base_code != 0:
            print(base_out[-2500:])
            print("\nA suite precisa passar antes de medir mutacao.")
            return 1

        falhas = 0
        for nome, antes, depois in MUTACOES:
            if antes not in ORIGINAL:
                print(f"[ERRO] anchor nao encontrado em: {nome}")
                falhas += 1
                continue
            ARQ.write_text(ORIGINAL.replace(antes, depois, 1), encoding="utf-8")
            code, out = rodar()
            detectou = code != 0
            print(f"[{'ok  ' if detectou else 'FALHOU'}] {nome}")
            if not detectou:
                print("        (a suite passou com o defeito de volta)")
                falhas += 1
            ARQ.write_text(ORIGINAL, encoding="utf-8")

        print()
        print(f"mutacoes nao detectadas: {falhas} de {len(MUTACOES)}")
        return 1 if falhas else 0
    finally:
        shutil.copy2(BACKUP, ARQ)
        BACKUP.unlink(missing_ok=True)
        print("arquivo restaurado:", ARQ.read_text(encoding="utf-8") == ORIGINAL)


if __name__ == "__main__":
    sys.exit(main())
