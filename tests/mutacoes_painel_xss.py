"""Valida por mutação o fix de XSS da tabela de fontes do painel.

O chat_id de fonte vem do banco e era interpolado em
onclick="testarConexaoFonteItem('${esc(id)}')" — as aspas escapadas
(HTML) voltam a viver na string JS, então um id com aspa virava código.
O fix: valor só em data-* (atributo escapado) + listener delegado.

Cada mutação é uma volta ao padrão anterior — a página continua abrindo,
mas a XSS volta. Os testes estruturais de test_painel_xss precisam pegar:
  1. botão "Testar" volta ao onclick interpolado;
  2. some o data-fonte-chat do botão (valor fora do atributo);
  3. some o listener delegado da tabela.
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
     "botao Testar volta pro onclick interpolado",
     '<button type="button" class="btn btn-neutro btn-sm" data-fonte-acao="testar" '
     'data-fonte-chat="${esc(chatId)}" title="Testar acesso">',
     '<button type="button" class="btn btn-neutro btn-sm" '
     'onclick="testarConexaoFonteItem(\'${esc(chatId)}\', this)" title="Testar acesso">'),
    (ARQ,
     "some o data-fonte-chat do botao Testar",
     '<button type="button" class="btn btn-neutro btn-sm" data-fonte-acao="testar" '
     'data-fonte-chat="${esc(chatId)}" title="Testar acesso">',
     '<button type="button" class="btn btn-neutro btn-sm" data-fonte-acao="testar" '
     'title="Testar acesso">'),
    (ARQ,
     "remove o listener delegado da tabela",
     '  $("#tabelaFontesTelegramCorpo")?.addEventListener("click", ev => {',
     '  // (mutacao) listener delegado removido'),
]

TESTE = "tests.test_painel_xss"
ARQUIVOS = ("ofertas/__init__.py", "ofertas/painel_html.py", "tests/test_painel_xss.py")


def preparar(base: Path) -> Path:
    sandbox = Path(tempfile.mkdtemp(prefix="mutxss-", dir=base))
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

    base = Path(tempfile.mkdtemp(prefix="mutxss-"))
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