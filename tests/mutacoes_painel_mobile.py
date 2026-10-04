"""Valida por mutação os ajustes mobile do painel.

Cada mutação desfaz um benefício: a página continua abrindo, mas o celular
perde toque sem delay, alvo de 44px, campo sem zoom, gaveta em largura total
ou a margem segura de entalhe. Os testes estruturais de test_painel_mobile
(que não precisam de navegador) precisam acusar cada reversão.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

ARQ = Path("ofertas/painel_html.py")
ORIGINAL = ARQ.read_text(encoding="utf-8")

# (arquivo, nome, antes, depois)
MUTACOES = [
    (ARQ,
     "viewport volta a ignorar a area segura (some viewport-fit)",
     '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
     '<meta name="viewport" content="width=device-width, initial-scale=1">'),
    (ARQ,
     "volta o delay de double-tap (some touch-action)",
     '  :where(a, button, input, select, textarea, [role="button"]) { touch-action: manipulation; }\n',
     ""),
    (ARQ,
     "alvo da nav volta a ser 9px de padding",
     "    .nav-item { min-width: 44px; min-height: 44px; justify-content: center; }\n",
     "    .nav-item { padding: 9px; }\n"),
    (ARQ,
     "campos voltam abaixo de 16px (zoom do iOS ao focar)",
     "    .campo input, .campo select, .saida-link input { font-size: 16px; }\n",
     ""),
    (ARQ,
     "gaveta volta ao maximo de 460px (faixa de fundo em tela pequena)",
     ".gaveta { max-width: 100%; }",
     ".gaveta { max-width: 460px; }"),
    (ARQ,
     "nav volta pro topo (some a barra de abas fixa do rodape)",
     "      position: fixed; bottom: 0; left: 0; right: 0; z-index: 40;\n",
     "      position: static; bottom: auto; left: auto; right: auto; z-index: auto;\n"),
    (ARQ,
     "botao do bot volta a encolher no fluxo do topo",
     ".bot-cartao { flex: none; max-width: 190px; }",
     ".bot-cartao { flex: 1 1 auto; }"),
]

TESTE = "tests.test_painel_mobile"
ARQUIVOS = ("ofertas/__init__.py", "ofertas/painel_html.py", "tests/test_painel_mobile.py")


def preparar(base: Path) -> Path:
    sandbox = Path(tempfile.mkdtemp(prefix="mutmobile-", dir=base))
    for arq in ARQUIVOS:
        origem = Path(arq)
        destino = sandbox / arq
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, destino)
    return sandbox


def rodar(sandbox: Path):
    env = dict(os.environ)
    proc = subprocess.run(
        [sys.executable, "-u", "-m", "unittest", TESTE],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(sandbox), env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr


def primeiro_falha(saida: str) -> str:
    for linha in saida.splitlines():
        if linha.startswith(("FAIL:", "ERROR:")):
            return linha.split(" (")[0]
    return "?"


def main() -> int:
    fora = [nome for arq, nome, antes, _ in MUTACOES if antes not in ORIGINAL]
    if fora:
        for nome in fora:
            print(f"[ERRO] anchor não encontrado em {ARQ.name}: {nome}", flush=True)
        return 2

    base = Path(tempfile.mkdtemp(prefix="mutmobile-"))
    try:
        primeiro = preparar(base)
        try:
            code, saida = rodar(primeiro)
        finally:
            shutil.rmtree(primeiro, ignore_errors=True)
        print(f"[base] codigo={code} -> {'PASSOU' if code == 0 else 'JA FALHA'}", flush=True)
        if code != 0:
            print(saida[-2500:], flush=True)
            return 1

        falhas = 0
        for arq, nome, antes, depois in MUTACOES:
            sandbox = preparar(base)
            alvo = sandbox / arq
            try:
                alvo.write_text(ORIGINAL.replace(antes, depois, 1), encoding="utf-8")
                code, saida = rodar(sandbox)
                print(f"[{'ok   ' if code != 0 else 'FALHOU'}] {nome}", flush=True)
                if code != 0:
                    print(f"          por {primeiro_falha(saida)}", flush=True)
                if code == 0:
                    falhas += 1
            finally:
                shutil.rmtree(sandbox, ignore_errors=True)

        print()
        print(f"mutações não detectadas: {falhas} de {len(MUTACOES)}", flush=True)
        return 1 if falhas else 0
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())