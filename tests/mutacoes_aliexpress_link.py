"""Valida por mutação que o link do AliExpress é SEMPRE o nosso, do produto.

As APIs de produto devolviam um `promotion_link` CONSTANTE e genérico
(best.aliexpress.com) para produtos diferentes — os posts iam com esse link.
O conserto: `_item_para_oferta` nunca confia no promotion_link; `converter` e
`buscar_ofertas` sempre geram o link via link.generate (_garantir_link_afiliado)
e, sem link gerado, o item é descartado. Cada ponto tem uma mutação:
  1. _item_para_oferta volta a confiar no promotion_link -> campo vaza cru;
  2. converter para de gerar e devolve a URL do produto como link -> post cru;
  3. buscar_ofertas volta ao guard antigo (usa url_afiliado cru) -> catálogo vazio.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

ARQ = Path("ofertas/sources/aliexpress.py")
ORIGINAL = ARQ.read_text(encoding="utf-8")

# (arquivo, nome, antes, depois)
MUTACOES = [
    (ARQ,
     "_item_para_oferta volta a confiar no promotion_link da API",
     '    url_afiliado = ""\n'
     '    url_produto = item.get("product_detail_url") or f"https://pt.aliexpress.com/item/{pid}.html" if pid else ""',
     '    url_afiliado = item.get("promotion_link") or ""\n'
     '    url_produto = item.get("product_detail_url") or f"https://pt.aliexpress.com/item/{pid}.html" if pid else ""'),
    (ARQ,
     "converter para de gerar o link e usa a URL do produto",
     "                oferta = _item_para_oferta(produtos_raw[0])\n"
     "                # promotion_link das APIs vem genérico/constante (ex.:\n"
     "                # best.aliexpress.com); o link do item exato com o nosso\n"
     "                # aff_fcid só sai do link.generate — sempre gerar.\n"
     "                _garantir_link_afiliado(oferta)\n"
     "                return oferta",
     "                oferta = _item_para_oferta(produtos_raw[0])\n"
     "                oferta.url_afiliado = oferta.url_produto\n"
     "                return oferta"),
    (ARQ,
     "buscar_ofertas volta ao guard antigo (sem gerar o link)",
     "            for p in produtos_raw:\n"
     "                oferta = _item_para_oferta(p)\n"
     "                if not (oferta.id_produto and oferta.url_produto):\n"
     "                    continue\n"
     "                try:\n"
     "                    _garantir_link_afiliado(oferta)\n"
     "                except Exception as e:\n"
     "                    log.warning(\"[ALIEXPRESS] Sem link de afiliado p/ %s: %s\",\n"
     "                                oferta.id_produto, e)\n"
     "                    continue\n"
     "                todas_ofertas[oferta.id_produto] = oferta",
     "            for p in produtos_raw:\n"
     "                oferta = _item_para_oferta(p)\n"
     "                if oferta.id_produto and oferta.url_afiliado:\n"
     "                    todas_ofertas[oferta.id_produto] = oferta"),
]

TESTE = "tests.test_aliexpress_link"
ARQUIVO_TESTE = "tests/test_aliexpress_link.py"


def preparar(base: Path) -> Path:
    sandbox = Path(tempfile.mkdtemp(prefix="ali-", dir=base))
    shutil.copytree("ofertas", sandbox / "ofertas")
    (sandbox / "tests").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ARQUIVO_TESTE, sandbox / ARQUIVO_TESTE)
    return sandbox


def rodar(sandbox: Path):
    # Sem rede e sem credenciais: os testes mockam `_chamar_api`,
    # `_obter_credenciais` e `gerar_link_afiliado`. Nenhum segredo é copiado.
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
    if ARQ.read_text(encoding="utf-8") != ORIGINAL:
        print(f"[ERRO] {ARQ.name} mudou durante a execução; abortando", flush=True)
        return 2
    nao_acha = [nome for arq, nome, antes, _ in MUTACOES if antes not in ORIGINAL]
    if nao_acha:
        for nome in nao_acha:
            print(f"[ERRO] anchor não encontrado em {ARQ.name}: {nome}", flush=True)
        return 2

    base = Path(tempfile.mkdtemp(prefix="mutali-"))
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
                alvo.write_text(ORIGINAL.replace(antes, depois, 1),
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