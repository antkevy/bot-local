"""Valida os testes novos por mutação: cada alteração tem de quebrar algo.

Teste que passa porque o código faz a coisa certa não prova que cobre a
coisa. Aqui cada mutação muda o comportamento de verdade, roda a suíte do
userbot e exige que ela reclame.

Cuidado já conhecido desta sessão: mutação que só muda um log é enganosa.
Todas abaixo mexem em fluxo, ordem ou recorte.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ARQ = Path("ofertas/sources/telegram_userbot.py")
ORIGINAL = ARQ.read_text(encoding="utf-8")
BACKUP = Path("ofertas/sources/telegram_userbot.py.bak_mutacao")

MUTACOES = [
    (
        "volta ao bug original: casa a fonte so pelo username que nao vem",
        "            chave = await _chave_do_chat(client, chat_id, chat_str, username_str)",
        "            chave = _chave_cadastrada(chat_str, username_str)",
    ),
    (
        "a resolucao sob demanda nunca popula o indice invertido",
        "            _indice_por_id[int(entidade.id)] = chave\n            log.info(\"[USERBOT] Fonte '%s' resolvida para o chat_id %s.\", chave, entidade.id)",
        "            log.info(\"[USERBOT] Fonte '%s' resolvida para o chat_id %s.\", chave, entidade.id)",
    ),
    (
        "nao monta o indice invertido (so popula o mapa por chave)",
        "    _indice_por_id[int(entidade.id)] = chave\n\n    for chave, chat_id in _ids_por_chave.items():",
        "    for chave, chat_id in _ids_por_chave.items():",
    ),
    (
        "nao trunca a recuperacao pelo teto",
        "        if len(perdidas) > MAX_MSG_RECUPERACAO:\n            perdidas = perdidas[:MAX_MSG_RECUPERACAO]\n",
        "",
    ),
    (
        "recupera historico inteiro de fonte que nunca capturou",
        "        if ultima <= 0:",
        "        if ultima < -1:",
    ),
    (
        "processa a recuperacao na ordem inversa (mais nova primeiro)",
        "        for mensagem in reversed(perdidas):",
        "        for mensagem in perdidas:",
    ),
    (
        "nao marca a mensagem como vista na fonte",
        "    db.marcar_ultima_mensagem_fonte(chave, message_id)\n    resultado = await pipeline",
        "    resultado = await pipeline",
    ),
    (
        "fonte nova com o bot no ar nunca e resolvida",
        "        if not chave or chave in _chaves_ja_resolvidas:",
        "        if True:",
    ),
    (
        "nao ignora a propria fonte desligada na recuperacao",
        "        if ultima <= 0:",
        "        if False:",
    ),
]


def rodar():
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_captura_userbot"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, proc.stdout + proc.stderr


def main():
    shutil.copy2(ARQ, BACKUP)
    try:
        base_code, base_out = rodar()
        print(f"[base] codigo={base_code} -> {'PASSOU' if base_code == 0 else 'JA FALHA'}")
        if base_code != 0:
            print(base_out[-2500:])
            print("\nA suite precisa passar antes de medir mutacao.")
            return 1

        falhas = 0
        for nome, antes, depois in MUTACOES:
            if antes not in ORIGINAL:
                print(f"[ERRO] anchor nao encontrado em: {nome}")
                falhas += 1
                continue
            ARQ.write_text(ORIGINAL.replace(antes, depois, 1), encoding="utf-8")
            code, out = rodar()
            detectou = code != 0
            print(f"[{'ok  ' if detectou else 'FALHOU'}] {nome}")
            if not detectou:
                falhas += 1
            ARQ.write_text(ORIGINAL, encoding="utf-8")

        print()
        print("mutacoes nao detectadas:", falhas)
        return 1 if falhas else 0
    finally:
        shutil.copy2(BACKUP, ARQ)
        BACKUP.unlink(missing_ok=True)
        print("arquivo restaurado:", ARQ.read_text(encoding="utf-8") == ORIGINAL)


if __name__ == "__main__":
    sys.exit(main())
