"""Valida por mutação as regras de link certo por fonte (Shopee e AliExpress).

Regras consolidadas nesta sessão de auditoria:
- Shopee: productOfferV2 usa itemId como filtro, não como garantia — a oferta
  sai do node do item pedido, nunca de nodes[0] de outro produto; URL sem
  itemId (loja/cupom/categoria) é descartada, não vira "Oferta Shopee".
- AliExpress: URL sem itemId (vitrine/wholesale/cupom) é descartada; o id que
  chega ao pipeline é sempre numérico (e_id_produto).

Cada ponto tem uma mutação sobre o fonte real (em sandbox):
  1. shopee volta a pegar nodes[0] -> outro produto sai com o nosso short link;
  2. shopee remove a guarda de itemId -> página de loja vira oferta;
  3. aliexpress remove a guarda de itemId -> vitrine vira oferta;
  4. aliexpress e_id_produto aceita qualquer id -> slug de página vira produto.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

FONTES = {
    "shopee": Path("ofertas/sources/shopee.py"),
    "aliexpress": Path("ofertas/sources/aliexpress.py"),
}
ORIGINAIS = {p: p.read_text(encoding="utf-8") for p in FONTES.values()}

# (fonte, nome, antes, depois)
MUTACOES = [
    (FONTES["shopee"],
     "shopee volta a pegar nodes[0] (outro produto com o nosso short link)",
     '    for node in nodes:\n'
     '        if str(node.get("itemId")) == str(item_id):\n'
     '            return _node_para_oferta(node)\n'
     '    if nodes:',
     '    if nodes:\n'
     '        return _node_para_oferta(nodes[0])\n'
     '    if nodes:'),
    (FONTES["shopee"],
     "shopee sem guarda de itemId (pagina de loja vira oferta)",
     '    if not item_id:\n'
     '        # Loja, cupom, categoria ou página desconhecida: não é produto. Gerar um\n'
     '        # short link aqui transformaria a página em "oferta" — chute, descarta.\n'
     '        raise RuntimeError("URL não é de produto Shopee (sem itemId)")',
     '    # (mutacao) guarda de itemId removida'),
    (FONTES["aliexpress"],
     "aliexpress sem guarda de itemId (vitrine vira oferta)",
     '    # URL sem id de item (vitrine, categoria, cupom, página desconhecida). Gerar\n'
     '    # um link aqui transformaria uma página de loja em "oferta" — inventar\n'
     '    # produto onde não há. Descarta (o pipeline tenta o próximo link).\n'
     '    if not item_id:\n'
     '        raise RuntimeError("URL não é de produto AliExpress (sem itemId)")',
     '    # (mutacao) guarda de itemId removida'),
    (FONTES["aliexpress"],
     "aliexpress e_id_produto aceita qualquer id (slug vira produto)",
     '    return bool(id_produto) and str(id_produto).isdigit()',
     '    return True'),
]

TESTE = "tests.test_aliexpress_link tests.test_shopee_link"
ARQUIVOS_TESTE = ["tests/test_aliexpress_link.py", "tests/test_shopee_link.py"]


def preparar(base: Path) -> Path:
    sandbox = Path(tempfile.mkdtemp(prefix="mutconv-", dir=base))
    shutil.copytree("ofertas", sandbox / "ofertas")
    (sandbox / "tests").mkdir(parents=True, exist_ok=True)
    for arq in ARQUIVOS_TESTE:
        shutil.copy2(arq, sandbox / arq)
    return sandbox


def rodar(sandbox: Path):
    # Sem rede e sem credenciais: os testes mockam `_chamar`/`_chamar_api`/
    # `gerar_link_afiliado`/`_obter_credenciais`. Nenhum segredo é copiado.
    env = dict(os.environ)
    proc = subprocess.run(
        [sys.executable, "-u", "-m", "unittest", *TESTE.split()],
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
    fora = [nome for arq, nome, antes, _ in MUTACOES if antes not in ORIGINAIS[arq]]
    if fora:
        for nome in fora:
            print(f"[ERRO] anchor não encontrado: {nome}", flush=True)
        return 2

    base = Path(tempfile.mkdtemp(prefix="mutconv-"))
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