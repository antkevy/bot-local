"""Valida por mutação as garantias da fonte Nerd Ofertas (feed do alerta.nerdofertas.com).

O feed é uma republished de canais de ofertas: ele entra no MESMO caminho das
mensagens do Telegram, e é aí que mora o risco. Cada garantia tem uma mutação:
  1. some com o corte do canal que é o próprio destino -> republica o que o
     canal de destino acabou de publicar;
  2. joga a foto fora na chamada do pipeline -> postagem sem foto;
  3. chama o pipeline sem a chave (source_id, message_id) -> dedup desligado,
     o mesmo alerta é postado de novo a cada ciclo;
  4. some com o gate de "fonte ativa" -> busca o feed com a fonte desligada.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

ARQ = Path("ofertas/sources/nerdofertas.py")
ORIGINAL = ARQ.read_text(encoding="utf-8")

# (arquivo, nome, antes, depois)
MUTACOES = [
    (ARQ,
     "processar_alertas para de ignorar o canal de destino",
     "        if e_canal_proprio(item, ignorados):\n"
     '            resumo["ignorados_proprio"] += 1\n'
     '            log.info("[NERDOFERTAS] Alerta %d ignorado: é do canal de destino.", item_id)\n'
     "            continue\n",
     ""),
    (ARQ,
     "processar_alertas joga a foto fora na chamada do pipeline",
     "                imagem_url=foto,\n",
     "                imagem_url=None,\n"),
    (ARQ,
     "processar_alertas chama o pipeline sem a chave de dedup",
     "                source_id=fonte_id,\n"
     "                message_id=item_id,\n",
     '                source_id="",\n'
     "                message_id=0,\n"),
    (ARQ,
     "processar_alertas perde o gate de fonte ativa",
     "    if not e_ativa():\n        return resumo\n",
     ""),
]

TESTE = "tests.test_nerdofertas"
ARQUIVO_TESTE = "tests/test_nerdofertas.py"


def preparar(base: Path) -> Path:
    sandbox = Path(tempfile.mkdtemp(prefix="nf-", dir=base))
    shutil.copytree("ofertas", sandbox / "ofertas")
    (sandbox / "tests").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ARQUIVO_TESTE, sandbox / ARQUIVO_TESTE)
    return sandbox


def rodar(sandbox: Path):
    # Sem rede e sem credenciais: os testes mockam o `sessao`, o download da
    # foto e o `pipeline.processar_mensagem_telegram`. Nenhum segredo é copiado.
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

    base = Path(tempfile.mkdtemp(prefix="mutnf-"))
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
