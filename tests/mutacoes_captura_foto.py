"""Valida os testes da foto do grupo por mutacao.

O conserto tem cinco partes, e cada mutacao desligaria exatamente uma:

  - a captura da foto na mensagem ao vivo (_baixar_foto);
  - o repasse dela pelo handler;
  - o repasse dela pela recuperacao de mensagens perdidas;
  - o repasse pelo _processar_mensagem_fonte (imagem_url=None fixo, o bug
    original);
  - a limpeza do banco no pipeline (bytes nao podem cair na coluna `imagem`).

Todas as cinco sao silenciosas no pior sentido: o post continua saindo, so
sem a foto — ou, na ultima, com bytes corrompendo a coluna que o painel le.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

ARQ_UB = Path("ofertas/sources/telegram_userbot.py")
ARQ_PIPE = Path("ofertas/pipeline.py")
ORIGINAIS = {a: a.read_text(encoding="utf-8") for a in (ARQ_UB, ARQ_PIPE)}

# (arquivo, nome da mutacao, antes, depois)
MUTACOES = [
    (ARQ_UB,
     "captura: sem foto na mensagem, ainda tenta baixar",
     '    if getattr(message, "photo", None) is None:\n        return None',
     '    if False:\n        return None'),
    (ARQ_UB,
     "handler ao vivo: deixa de repassar a foto",
     "            foto = await _baixar_foto(client, event.message)\n"
     "            await _processar_mensagem_fonte(chave, texto, event.id, bot_poster, dry_run,\n"
     "                                            imagem_url=foto)",
     "            await _processar_mensagem_fonte(chave, texto, event.id, bot_poster, dry_run)"),
    (ARQ_UB,
     "_processar_mensagem_fonte: volta a fixar imagem_url=None",
     "        imagem_url=imagem_url,",
     "        imagem_url=None,"),
    (ARQ_UB,
     "recuperacao de perdidas: deixa de repassar a foto",
     "            foto = await _baixar_foto(client, mensagem)\n"
     "            await _processar_mensagem_fonte(chave, texto, mensagem.id, bot_poster, dry_run,\n"
     "                                            imagem_url=foto)",
     "            await _processar_mensagem_fonte(chave, texto, mensagem.id, bot_poster, dry_run)"),
    (ARQ_PIPE,
     "pipeline: limpeza do banco desligada (bytes entram na coluna)",
     "        foto_da_mensagem = isinstance(oferta.imagem, (bytes, bytearray))",
     "        foto_da_mensagem = False"),
]

TESTES = ("tests.test_captura_userbot", "tests.test_escolha_link",
          "tests.test_dados_oferta")
ARQUIVOS_TEMAS = ("tests/test_captura_userbot.py", "tests/test_escolha_link.py",
                  "tests/test_dados_oferta.py", "tests/isolamento.py")


def preparar(base: Path) -> Path:
    sandbox = Path(tempfile.mkdtemp(prefix="foto-", dir=base))
    shutil.copytree("ofertas", sandbox / "ofertas")
    (sandbox / "tests").mkdir(parents=True, exist_ok=True)
    for arq in ARQUIVOS_TEMAS:
        shutil.copy2(arq, sandbox / arq)
    return sandbox


def rodar(sandbox: Path):
    env = dict(os.environ)
    # Sem .env, config.chat_id fica vazio e o pipeline SOME antes de postar:
    # o teste do banco passaria sem testar nada. O env faz o caminho real
    # rodar no sandbox sem copiar credenciais.
    env.setdefault("TELEGRAM_CHAT_ID", "-100999999999")
    proc = subprocess.run(
        [sys.executable, "-u", "-m", "unittest", *TESTES],
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
            print(f"[ERRO] {arq} mudou durante a execucao; abortando", flush=True)
            return 2
    nao_acha = [(a, nome) for a, nome, antes, _ in MUTACOES if antes not in ORIGINAIS[a]]
    if nao_acha:
        for a, nome in nao_acha:
            print(f"[ERRO] anchor nao encontrado em {a.name}: {nome}", flush=True)
        return 2

    base = Path(tempfile.mkdtemp(prefix="mutfoto-"))
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
        print(f"mutacoes nao detectadas: {falhas} de {len(MUTACOES)}", flush=True)
        return 1 if falhas else 0
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())