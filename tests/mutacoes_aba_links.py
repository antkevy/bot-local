"""Valida por mutação o caminho dos dados da aba Links.

A aba passou a mostrar foto do produto, link original e link de afiliado.
O original (`url_produto`) é a única peça nova no banco; cada ponto do
caminho tem uma mutação:
  1. a migração (ALTER TABLE) perder a coluna -> registrar() quebra;
  2. o INSERT do registrar() omitir o original -> linha sai sem ele;
  3. o SELECT do listar_postadas() omitir o original -> painel sem dado;
  4. obter_metricas() não expor url_original/imagem -> aba sem o novo campo.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

ARQ_DB = Path("ofertas/db.py")
ARQ_PAINEL = Path("ofertas/painel.py")
ORIGINAIS = {a: a.read_text(encoding="utf-8") for a in (ARQ_DB, ARQ_PAINEL)}

# (arquivo, nome, antes, depois)
MUTACOES = [
    (ARQ_DB,
     "migracao: ALTER TABLE perde a coluna url_produto",
     '    for coluna in ("url_afiliado", "imagem", "url_produto"):',
     '    for coluna in ("url_afiliado", "imagem"):'),
    (ARQ_DB,
     "registrar: INSERT omite o link original",
     "            \" (uid, plataforma, titulo, preco, url_afiliado, imagem,\"",
     "            \" (uid, plataforma, titulo, preco, url_afiliado, imagem)\""),
    (ARQ_DB,
     "listar_postadas: SELECT omite o link original",
     "            \"SELECT uid, plataforma, titulo, preco, url_afiliado, imagem,\"",
     "            \"SELECT uid, plataforma, titulo, preco, url_afiliado, imagem\""),
    (ARQ_PAINEL,
     "obter_metricas: aba nao expoe url_original",
     '            "url_original": (p.get("url_produto") or "").strip(),\n',
     ""),
]

TESTE = "tests.test_aba_links"
ARQUIVO_TESTE = "tests/test_aba_links.py"


def preparar(base: Path) -> Path:
    sandbox = Path(tempfile.mkdtemp(prefix="links-", dir=base))
    shutil.copytree("ofertas", sandbox / "ofertas")
    (sandbox / "tests").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ARQUIVO_TESTE, sandbox / ARQUIVO_TESTE)
    return sandbox


def rodar(sandbox: Path):
    # Sem portas de rede abertas do painel: o teste importa o módulo e chama
    # obter_metricas(), que só lê o banco. Nenhuma credencial é copiada.
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
    for arq, original in ORIGINAIS.items():
        if arq.read_text(encoding="utf-8") != original:
            print(f"[ERRO] {arq} mudou durante a execução; abortando", flush=True)
            return 2
    nao_acha = [(a, nome) for a, nome, antes, _ in MUTACOES if antes not in ORIGINAIS[a]]
    if nao_acha:
        for a, nome in nao_acha:
            print(f"[ERRO] anchor não encontrado em {a.name}: {nome}", flush=True)
        return 2

    base = Path(tempfile.mkdtemp(prefix="mutlinks-"))
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