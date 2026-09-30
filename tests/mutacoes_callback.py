"""Valida por mutação o fix do callback das prévias e do /addfonte.

- A ação fora do catálogo (post/drop) deve ser rejeitada ANTES de consumir
  o token; e o post não pode derrubar o handler quando falha.
- O /addfonte deve validar o formato do chat_id antes de gravar (porta de
  entrada do XSS do painel).

Cada mutação volta ao padrão frágil e os testes precisam pegá-la:
  1. pop do token volta para ANTES da validação de ação;
  2. post sem try/except (erro derruba o handler);
  3. guarda de formato do /addfonte removida (chat_id cru entra no banco).
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

ARQ = Path("ofertas/bot_interativo.py")
ORIGINAL = ARQ.read_text(encoding="utf-8")

# (arquivo, nome, antes, depois)
MUTACOES = [
    (ARQ,
     "_callback consome o token antes de validar a acao",
     '    acao, _, token = (q.data or "").partition(":")\n'
     '    if acao not in _ACOES_CALLBACK:',
     '    acao, _, token = (q.data or "").partition(":")\n'
     '    oferta = _pendentes.pop(token, None)\n'
     '    if acao not in _ACOES_CALLBACK:'),
    (ARQ,
     "_callback sem try/except no post (erro derruba o handler)",
     '    try:\n'
     '        if acao == "post":\n'
     '            await postar_oferta(ctx.bot, oferta, config.chat_id)\n'
     '            db.registrar(oferta)\n'
     '            await _editar_previa(q, "✅ Postada no canal!")\n'
     '        else:\n'
     '            await _editar_previa(q, "🗑 Descartada.")\n'
     '    except Exception as e:\n'
     '        # Falha ao publicar (rede, Telegram) não pode derrubar o handler sem\n'
     '        # deixar o dono saber o que houve com a prévia.\n'
     '        log.exception("[CALLBACK] Falha ao processar ação %s", acao)\n'
     '        await _editar_previa(q, f"❌ Erro ao processar: {e}")',
     '    if acao == "post":\n'
     '        await postar_oferta(ctx.bot, oferta, config.chat_id)\n'
     '        db.registrar(oferta)\n'
     '        await _editar_previa(q, "✅ Postada no canal!")\n'
     '    else:\n'
     '        await _editar_previa(q, "🗑 Descartada.")'),
    (ARQ,
     "/addfonte sem guarda de formato (chat_id cru vai pro banco)",
     '    if not _chat_id_valido(chat_id):\n'
     '        await update.message.reply_text(\n'
     '            "❌ Formato inválido. Use o id do chat (ex.: `-1001234567890`), "\n'
     '            "`@username` ou link `t.me/...` do canal/grupo.",\n'
     '            parse_mode="Markdown",\n'
     '        )\n'
     '        return',
     '    # (mutacao) guarda de formato removida'),
]

TESTE = "tests.test_callback_previa tests.test_add_fonte"
ARQUIVOS_TESTE = ["tests/test_callback_previa.py", "tests/test_add_fonte.py"]


def preparar(base: Path) -> Path:
    sandbox = Path(tempfile.mkdtemp(prefix="mutcb-", dir=base))
    shutil.copytree("ofertas", sandbox / "ofertas")
    (sandbox / "tests").mkdir(parents=True, exist_ok=True)
    for arq in ARQUIVOS_TESTE:
        shutil.copy2(arq, sandbox / arq)
    return sandbox


def rodar(sandbox: Path):
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
    fora = [nome for arq, nome, antes, _ in MUTACOES if antes not in ORIGINAL]
    if fora:
        for nome in fora:
            print(f"[ERRO] anchor não encontrado em {ARQ.name}: {nome}", flush=True)
        return 2

    base = Path(tempfile.mkdtemp(prefix="mutcb-"))
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