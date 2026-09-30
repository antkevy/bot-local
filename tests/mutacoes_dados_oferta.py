"""Valida os testes de dados das fontes por mutacao.

Cada mutacao remove ou quebra exatamente um comportamento que os testes de
`test_dados_oferta.py` deveriam estar defendendo: a nota da Amazon com
virgula que vira 4,8, o 'mil' do ML que multiplica por mil, o '0' da Shopee
que vira None. Sao todas mudancas silenciosas no sentido pior: o formato da
legenda continua correto, o post continua saindo — so com o numero errado ou
com selo repetido.

Roda em sandbox descartavel (copia o pacote ofertas inteiro + o teste). Nenhum
teste aqui toca rede: os parsers comem dados congelados/sinteticos.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

ARQ_SHOPEE = Path("ofertas/sources/shopee.py")
ARQ_AMAZON = Path("ofertas/sources/amazon.py")
ARQ_MERCADO = Path("ofertas/sources/mercadolivre.py")
ORIGINAIS = {a: a.read_text(encoding="utf-8") for a in
             (ARQ_SHOPEE, ARQ_AMAZON, ARQ_MERCADO)}

# (arquivo, nome da mutacao, antes, depois)
MUTACOES = [
    (ARQ_SHOPEE,
     "shopee: a nota deixa de entrar no campo avaliacao",
     "        avaliacao=_nota_de(n),\n        vendas=_vendas_de(n),\n    )",
     "    )"),
    (ARQ_SHOPEE,
     "shopee: a nota fora da faixa (0, 9.9) volta a ser aceita",
     "    return round(nota, 1) if 0 < nota <= 5 else None",
     "    return round(nota, 1)"),
    (ARQ_SHOPEE,
     "shopee: vendas 0 volta a ser numero",
     "    return qtd if qtd > 0 else None",
     "    return qtd"),
    (ARQ_AMAZON,
     "amazon: a virgula brasileira deixa de virar ponto",
     '        nota = float(bruto.replace(".", "").replace(",", ".")) if "," in bruto else float(bruto)',
     "        nota = float(bruto)"),
    (ARQ_AMAZON,
     "amazon: _card_para_oferta deixa de gravar a nota",
     "        avaliacao=_nota_do_card(card),",
     ""),
    (ARQ_MERCADO,
     "ml: o 'mil' deixa de multiplicar por mil",
     "        if m.group(2):\n            qtd *= 1000",
     "        qtd = qtd"),
    (ARQ_MERCADO,
     "ml: _parse_card deixa de gravar nota e vendas",
     "        avaliacao=avaliacao,\n        vendas=vendas,",
     ""),
]


def preparar(base: Path) -> Path:
    sandbox = Path(tempfile.mkdtemp(prefix="dods-", dir=base))
    shutil.copytree("ofertas", sandbox / "ofertas")
    (sandbox / "tests").mkdir(parents=True, exist_ok=True)
    shutil.copy2("tests/test_dados_oferta.py", sandbox / "tests/test_dados_oferta.py")
    return sandbox


def rodar(sandbox: Path):
    proc = subprocess.run(
        [sys.executable, "-u", "-m", "unittest", "tests.test_dados_oferta"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(sandbox),
    )
    return proc.returncode, proc.stdout + proc.stderr


def primeiro_falha(saida: str) -> str:
    for linha in saida.splitlines():
        if linha.startswith(("FAIL:", "ERROR:")):
            return linha.split(" (")[0]
    return "?"


def main() -> int:
    # guarda: nada pode ter mudado de enfoque entre a criacao e a rodada
    for arq, original in ORIGINAIS.items():
        if arq.read_text(encoding="utf-8") != original:
            print(f"[ERRO] {arq} mudou durante a execucao; abortando", flush=True)
            return 2
    nao_acha = [(a, nome) for a, nome, antes, _ in MUTACOES if antes not in ORIGINAIS[a]]
    if nao_acha:
        for a, nome in nao_acha:
            print(f"[ERRO] anchor nao encontrado em {a.name}: {nome}", flush=True)
        return 2

    base = Path(tempfile.mkdtemp(prefix="mutdods-"))
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
                original = ORIGINAIS[arq]
                alvo.write_text(original.replace(antes, depois, 1), encoding="utf-8")
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
        print(f"mutacoes nao detectadas: {falhas} de {len(MUTACOES)}", flush=True)
        return 1 if falhas else 0
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())