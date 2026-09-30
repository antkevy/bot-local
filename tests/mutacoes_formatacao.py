"""Valida por mutacao os dois ajustes de formatacao:

  - o preco sem 'De:' deixou de sair como '💰 R$ 123,45' e passou a '✅ Por:'
    (formatter) — um revert para a moeda nao pode passar despercebido;
  - o card do Mercado Livre nao anuncia mais 'Frete gratis' nem 'preco no
    Pix' (origem em _parse_card) — ressuscitar qualquer um dos dois selos
    tem de quebrar um teste.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

ARQ_FMT = Path("ofertas/formatter.py")
ARQ_ML = Path("ofertas/sources/mercadolivre.py")
ORIGINAIS = {a: a.read_text(encoding="utf-8") for a in (ARQ_FMT, ARQ_ML)}

# (arquivo, nome, antes, depois)
MUTACOES = [
    (ARQ_FMT,
     "formatter: preco sem 'De:' volta a sair como '💰'",
     '        linhas.append(f"✅ Por: <b>{preco_br(preco)}</b>")',
     '        linhas.append(f"💰 <b>{preco_br(preco)}</b>")'),
    (ARQ_ML,
     "_parse_card: selo 'Frete gratis' ressuscitado no extra",
     "        extra=None,",
     '        extra="🚚 Frete grátis" if "Frete grátis" in card.get_text() else None,'),
    (ARQ_ML,
     "_parse_card: selo 'preço no Pix' ressuscitado no extra",
     "        extra=None,",
     '        extra="💠 preço no Pix",'),
]

TESTE = "tests.test_dados_oferta"
ARQUIVO_TESTE = "tests/test_dados_oferta.py"


def preparar(base: Path) -> Path:
    sandbox = Path(tempfile.mkdtemp(prefix="fmt-", dir=base))
    shutil.copytree("ofertas", sandbox / "ofertas")
    (sandbox / "tests").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ARQUIVO_TESTE, sandbox / ARQUIVO_TESTE)
    return sandbox


def rodar(sandbox: Path):
    env = dict(os.environ)  # sem credenciais: nenhum modulo de rede e tocado
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
    for arq, original in ORIGINAIS.items():
        if arq.read_text(encoding="utf-8") != original:
            print(f"[ERRO] {arq} mudou durante a execução; abortando", flush=True)
            return 2
    nao_acha = [(a, nome) for a, nome, antes, _ in MUTACOES if antes not in ORIGINAIS[a]]
    if nao_acha:
        for a, nome in nao_acha:
            print(f"[ERRO] anchor não encontrado em {a.name}: {nome}", flush=True)
        return 2

    base = Path(tempfile.mkdtemp(prefix="mutfmt-"))
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
                alvo.write_text(ORIGINAIS[arq].replace(antes, depois, 1),
                                encoding="utf-8")
                code, saida = rodar(sandbox)
                achou = primeiro_falha(saida) if code != 0 else ""
                print(f"[{'ok   ' if code != 0 else 'FALHOU'}] {nome}", flush=True)
                if code != 0:
                    print(f"          por {achou}", flush=True)
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