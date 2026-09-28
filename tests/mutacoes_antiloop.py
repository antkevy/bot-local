"""Valida os testes do anti-loop por mutação.

A mutação que importa é a volta do `lstrip("-100")`: é o defeito real que
estava no código, e ela precisa ser detectada.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ARQ = Path("ofertas/bot_interativo.py")
ORIGINAL = ARQ.read_text(encoding="utf-8")
BACKUP = Path("ofertas/bot_interativo.py.bak_mutacao")

MUTACOES = [
    (
        "volta ao lstrip, que apaga o conjunto {'-','1','0'} e nao o prefixo",
        '    curto = dest_id.removeprefix("-100")\n'
        '    return source_id in (dest_id, curto, "-100" + curto)',
        '    return source_id in (dest_id, dest_id.lstrip("-100"))',
    ),
    (
        "so compara com o prefixo, e ignora o id sem prefixo",
        '    return source_id in (dest_id, curto, "-100" + curto)',
        '    return source_id in (dest_id, "-100" + curto)',
    ),
    (
        "so compara o destino como veio, e ignora a forma normalizada",
        '    return source_id in (dest_id, curto, "-100" + curto)',
        '    return source_id in (dest_id, curto)',
    ),
    (
        "aceita prefixo parcial e trava a publicacao no destino",
        '    return source_id in (dest_id, curto, "-100" + curto)',
        '    return source_id == dest_id or dest_id.startswith(source_id.lstrip("-"))',
    ),
    (
        "destino vazio deixa de ser rejeitado e '-100' casa com ele",
        '    if not source_id or not dest_id:\n        return False',
        '    if not source_id:\n        return False',
    ),
]


def rodar():
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_antiloop"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, proc.stdout + proc.stderr


def main():
    shutil.copy2(ARQ, BACKUP)
    try:
        base_code, base_out = rodar()
        print(f"[base] codigo={base_code} -> {'PASSOU' if base_code == 0 else 'JA FALHA'}")
        if base_code != 0:
            print(base_out[-2000:])
            return 1

        falhas = 0
        for nome, antes, depois in MUTACOES:
            if antes not in ORIGINAL:
                print(f"[ERRO] anchor nao encontrado em: {nome}")
                falhas += 1
                continue
            ARQ.write_text(ORIGINAL.replace(antes, depois, 1), encoding="utf-8")
            code, _ = rodar()
            detectou = code != 0
            print(f"[{'ok  ' if detectou else 'FALHOU'}] {nome}")
            if not detectou:
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
