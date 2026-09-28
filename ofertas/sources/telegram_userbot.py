"""Cliente Userbot (Telethon) para monitorar canais e grupos de terceiros no Telegram.

Permite que a conta pessoal do usuário monitore canais públicos (ex: @promos) ou
grupos/canais privados onde o usuário já é membro, sem precisar adicionar o bot
como administrador. As mensagens são enviadas diretamente ao pipeline central.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from telethon import TelegramClient, events

from .. import db, pipeline
from ..config import config
from .telegram_scraper import e_postagem_propria

log = logging.getLogger("ofertas.userbot")

_cliente_global: TelegramClient | None = None
_tarefa_monitor: asyncio.Task | None = None

# Índice invertido id numérico do Telegram -> chave da fonte como está no
# banco ("@nerdofertas"). Ver `_montar_indice_fontes` para por que o caminho
# inverso (achar a chave pelo username) não funciona.
_indice_por_id: dict[int, str] = {}
_ids_por_chave: dict[str, int] = {}
_chaves_ja_resolvidas: set[str] = set()

# Teto de mensagens recuperadas por fonte quando o bot volta do ar. Sem teto,
# uma fonte que ficou dias sem ser lida despejaria o histórico inteiro no
# canal de destino de uma vez.
MAX_MSG_RECUPERACAO = 50


def tem_credenciais() -> bool:
    """Verifica se as credenciais de API do Telegram (my.telegram.org) estão preenchidas."""
    return bool(config.telegram_api_id and config.telegram_api_hash)


def tem_sessao_salva() -> bool:
    """Verifica se o arquivo de sessão do Telethon já foi gerado."""
    caminho = Path(f"{config.telegram_session}.session")
    return caminho.exists() and caminho.stat().st_size > 0


def obter_cliente() -> TelegramClient:
    """Retorna a instância do cliente Telethon."""
    global _cliente_global
    if _cliente_global is None:
        if not tem_credenciais():
            raise ValueError("TELEGRAM_API_ID ou TELEGRAM_API_HASH não configurados no .env")
        _cliente_global = TelegramClient(
            config.telegram_session,
            config.telegram_api_id,
            config.telegram_api_hash,
        )
    return _cliente_global


async def login_terminal() -> bool:
    """Realiza o login interativo via terminal para salvar a sessão do Telethon."""
    if not tem_credenciais():
        print("\n❌ Erro: Configure TELEGRAM_API_ID e TELEGRAM_API_HASH no arquivo .env primeiro.")
        print("👉 Obtenha gratuitamente em: https://my.telegram.org (seção 'API development tools')\n")
        return False

    client = obter_cliente()
    print("\n📱 Iniciando autenticação da sua conta Telegram...")
    await client.start()

    me = await client.get_me()
    nome = f"{me.first_name or ''} {me.last_name or ''}".strip()
    username = f"@{me.username}" if me.username else ""
    print(f"\n🎉 Sucesso! Conectado como: {nome} {username} (ID: {me.id})")
    print(f"📁 Sessão salva em: {config.telegram_session}.session\n")
    await client.disconnect()
    return True


async def testar_conexao() -> dict[str, Any]:
    """Testa se a sessão atual do Userbot está autenticada e pronta para uso."""
    if not tem_credenciais():
        return {"ok": False, "motivo": "Credenciais TELEGRAM_API_ID / TELEGRAM_API_HASH ausentes no .env"}
    if not tem_sessao_salva():
        return {"ok": False, "motivo": "Sessão não autenticada. Execute: uv run python -m ofertas telegram-user-login"}

    try:
        client = obter_cliente()
        if not client.is_connected():
            await client.connect()
        if not await client.is_user_authorized():
            return {"ok": False, "motivo": "Sessão expirada ou não autorizada."}
        me = await client.get_me()
        return {
            "ok": True,
            "user_id": me.id,
            "nome": f"{me.first_name or ''} {me.last_name or ''}".strip(),
            "username": me.username or "",
            "telefone": me.phone or "",
        }
    except Exception as e:
        log.error("Erro ao testar conexão do Telethon Userbot: %s", e)
        return {"ok": False, "motivo": str(e)}


def _chave_cadastrada(chat_str: str, username_str: str) -> str | None:
    """A chave da fonte que este chat corresponde, ou None se não for fonte.

    Aceita as três formas em que o dono pode ter cadastrado o grupo: id
    completo do Telegram ("-1001755551234"), id curto ("1755551234") e
    @username.

    O id curto usava `str.lstrip("-100")`, e isso é remova o conjunto de
    caracteres {'-', '1', '0'} da esquerda, não o prefixo: "-1001234567890"
    virava "234567890", comendo o primeiro dígito do id. Uma fonte cadastrada
    pelo id curto recebia zero mensagens, e nenhuma mensagem era gravada em
    log para explicar — silêncio puro.
    """
    cadastradas = {
        str(f["chat_id"]).strip().lower()
        for f in db.listar_fontes_telegram(ativas_apenas=True)
    }
    for candidata in (chat_str, chat_str.removeprefix("-100"), username_str):
        if candidata and candidata.lower() in cadastradas:
            return next(c for c in cadastradas if c == candidata.lower())
    return None


async def _montar_indice_fontes(client: TelegramClient, fontes: list[dict]) -> None:
    """Resolve, uma vez no startup, o id numérico de cada fonte cadastrada.

    O caminho óbvio para casar uma mensagem com sua fonte é o username: o
    handler montava "@nerdofertas" a partir de `chat.username` e procurava no
    banco. Só que `chat.username` chega `None` para canais — o Telethon traz o
    que está no cache de entidades da sessão, e o `get_entity` do canal devolve
    título e id, não o username. Aí `_chave_cadastrada` recebia `""` como
    username, nenhuma das três candidatas ("1465877129", "1465877129", "")
    batia com "@nerdofertas", e o handler voltava em silêncio: nenhuma linha de
    log, `ultima_msg_id` congelado no zero, `mensagens_telegram` vazio — o
    scraper "funcionando" e capturando nada.

    O id numérico não tem essa fragilidade: é o mesmo número dos dois lados.
    Resolve-se cada fonte uma vez e guarda-se o índice invertido.
    """
    _indice_por_id.clear()
    _ids_por_chave.clear()
    _chaves_ja_resolvidas.clear()

    for fonte in fontes:
        chave = str(fonte["chat_id"]).strip()
        if not chave:
            continue
        _chaves_ja_resolvidas.add(chave)
        try:
            entidade = await client.get_entity(chave)
        except Exception as e:
            log.warning("[USERBOT] Não consegui resolver a fonte '%s': %s", chave, e)
            continue
        if entidade is None:
            log.warning("[USERBOT] A fonte '%s' não devolveu entidade no Telegram.", chave)
            continue
        _ids_por_chave[chave] = int(entidade.id)
        _indice_por_id[int(entidade.id)] = chave

    for chave, chat_id in _ids_por_chave.items():
        log.info("[USERBOT] Fonte '%s' resolvida para o chat_id %s.", chave, chat_id)

    sem_id = [str(f["chat_id"]) for f in fontes if str(f["chat_id"]).strip() not in _ids_por_chave]
    if sem_id:
        log.warning("[USERBOT] %d fonte(s) sem id do Telegram e serão ignoradas: %s",
                    len(sem_id), ", ".join(sem_id))


async def _chave_do_chat(client: TelegramClient, chat_id: int, chat_str: str, username_str: str) -> str | None:
    """A chave cadastrada deste chat, ou None se não for fonte."""
    if chat_id in _indice_por_id:
        return _indice_por_id[chat_id]

    # Chave nova cadastrada com o bot já no ar: ainda não está no índice.
    # Só custa uma resolução, e só uma vez por chave sem id.
    for fonte in db.listar_fontes_telegram(ativas_apenas=True):
        chave = str(fonte["chat_id"]).strip()
        if not chave or chave in _chaves_ja_resolvidas:
            continue
        _chaves_ja_resolvidas.add(chave)
        try:
            entidade = await client.get_entity(chave)
        except Exception as e:
            log.warning("[USERBOT] Não consegui resolver a fonte '%s': %s", chave, e)
            continue
        if entidade is not None:
            _ids_por_chave[chave] = int(entidade.id)
            _indice_por_id[int(entidade.id)] = chave
            log.info("[USERBOT] Fonte '%s' resolvida para o chat_id %s.", chave, entidade.id)
            break

    if chat_id in _indice_por_id:
        return _indice_por_id[chat_id]
    return _chave_cadastrada(chat_str, username_str)


async def _processar_mensagem_fonte(
    chave: str, texto: str, message_id: int, bot_poster: Any, dry_run: bool
) -> None:
    """Marca a mensagem como vista e entrega o texto ao pipeline.

    Único caminho para o pipeline: o que chega ao vivo e o que é recuperado
    depois ficam idênticos, inclusive no registro de "já vi esta mensagem".
    """
    db.marcar_ultima_mensagem_fonte(chave, message_id)
    resultado = await pipeline.processar_mensagem_telegram(
        texto=texto,
        imagem_url=None,
        source_id=chave,
        message_id=message_id,
        bot=bot_poster,
        dry_run=dry_run,
    )
    if resultado.get("ok"):
        log.info("[USERBOT] ✅ Oferta da fonte %s processada com sucesso!", chave)
    else:
        log.info("[USERBOT] ℹ️ Mensagem da fonte %s não publicada: %s", chave, resultado.get("motivo"))


async def _recuperar_perdidas(
    client: TelegramClient, bot_poster: Any, dry_run: bool
) -> int:
    """Reprocessa o que foi postado enquanto o bot não estava olhando.

    Uma fonte só recebe update do Telegram enquanto o userbot está conectado.
    Entre um reinício e o outro, o canal continua postando e essas mensagens
    existem no histórico — mas nunca chegam como update. Sem isto, cada
    parada do bot vira uma janela de ofertas perdidas, silenciosamente.

    Só recupera a partir de `ultima_msg_id`. Com a marcação zerada (fonte
    nunca capturou nada) não há onde recuar, e reprocessar o histórico inteiro
    de um canal com 140 mil mensagens inundaria o destino.
    """
    total = 0
    for fonte in db.listar_fontes_telegram(ativas_apenas=True):
        chave = str(fonte["chat_id"]).strip()
        ultima = int(fonte.get("ultima_msg_id") or 0)
        if ultima <= 0:
            log.info("[USERBOT] Fonte '%s' nunca capturou nada — começando do zero, sem histórico.", chave)
            continue
        chat_id_num = _ids_por_chave.get(chave)
        if chat_id_num is None:
            log.warning("[USERBOT] Sem id do Telegram para recuperar a fonte '%s'.", chave)
            continue

        try:
            entidade = await client.get_entity(chat_id_num)
            perdidas = [
                m async for m in client.iter_messages(
                    entidade, min_id=ultima, limit=MAX_MSG_RECUPERACAO
                )
            ]
        except Exception as e:
            log.warning("[USERBOT] Falha ao recuperar mensagens da fonte '%s': %s", chave, e)
            continue

        # O teto é aplicado aqui, e não só pedido ao `iter_messages`: depender
        # de o cliente respeitar `limit` deixa o limite sem dono no dia em que
        # oTelethon mudar de comportamento. `iter_messages` traz do mais novo
        # para o mais velho, então o corte fica no fim.
        if len(perdidas) > MAX_MSG_RECUPERACAO:
            perdidas = perdidas[:MAX_MSG_RECUPERACAO]

        if not perdidas:
            continue
        # O pipeline espera a ordem em que o canal publicou.
        log.info("[USERBOT] Recuperando %d mensagem(ns) perdidas da fonte '%s'...",
                 len(perdidas), chave)
        for mensagem in reversed(perdidas):
            texto = mensagem.raw_text or ""
            if not texto:
                continue
            if e_postagem_propria(mensagem.chat_id, destination_chat_id=config.chat_id):
                continue
            await _processar_mensagem_fonte(chave, texto, mensagem.id, bot_poster, dry_run)
            total += 1
    return total


async def iniciar_userbot(bot_poster: Any, dry_run: bool | None = None) -> bool:
    """Inicia o Userbot em segundo plano para monitorar as fontes cadastradas."""
    global _tarefa_monitor
    if not tem_credenciais() or not tem_sessao_salva():
        log.info("[USERBOT] Userbot desligado (credenciais ausentes ou sessão não logada).")
        return False

    if dry_run is None:
        dry_run = bool(config.fonte_telegram.get("dry_run", False))

    client = obter_cliente()
    if not client.is_connected():
        await client.connect()

    if not await client.is_user_authorized():
        log.warning("[USERBOT] Sessão do Telethon não autorizada. Execute: uv run python -m ofertas telegram-user-login")
        return False

    me = await client.get_me()
    log.info("[USERBOT] Conectado como %s (@%s, ID: %s)", me.first_name, me.username, me.id)

    # Obter lista de fontes ativas
    fontes_db = db.listar_fontes_telegram(ativas_apenas=True)
    await _montar_indice_fontes(client, fontes_db)

    # Handler de novas mensagens
    @client.on(events.NewMessage)
    async def _ao_receber_mensagem(event: events.NewMessage.Event):
        try:
            chat = await event.get_chat()
            chat_id = getattr(chat, "id", None) or event.chat_id
            username = getattr(chat, "username", None) or ""
            chat_str = str(chat_id)
            username_str = f"@{username.lower()}" if username else ""

            # Verificar se este chat/canal está na lista de fontes ativas.
            # Devolvemos a chave COMO ESTÁ CADASTRADA, e não o id numérico
            # resolvido: a fonte pode ter sido salva como "@nerdofertas" ou
            # como "-1001755...", e é por essa chave que o banco está
            # indexado. Usar o id resolvido aqui fazia todo UPDATE de
            # "última captura" cair em zero linhas, e a tela do painel mostrava
            # para sempre a data em que a fonte foi cadastrada.
            chave = await _chave_do_chat(client, chat_id, chat_str, username_str)
            if chave is None:
                return

            texto = event.raw_text or event.message.message or ""
            if not texto:
                return

            # Anti-Loop: Não processar se for o próprio canal de destino do bot
            if e_postagem_propria(chat_id, destination_chat_id=config.chat_id):
                log.debug("[USERBOT] Ignorando mensagem originada no próprio canal de destino: %s", chat_id)
                return

            log.info("[USERBOT] Nova mensagem capturada do canal/grupo %s (ID: %s, Msg: %s)", getattr(chat, "title", username), chat_id, event.id)

            await _processar_mensagem_fonte(chave, texto, event.id, bot_poster, dry_run)

        except Exception as e:
            log.error("[USERBOT] Erro ao processar mensagem do evento Telethon: %s", e)

    log.info("[USERBOT] Monitorando %d fontes ativas do Telegram em tempo real.", len(fontes_db))

    try:
        recuperadas = await _recuperar_perdidas(client, bot_poster, dry_run)
        if recuperadas:
            log.info("[USERBOT] %d mensagem(ns) recuperada(s) que chegaram durante a parada.", recuperadas)
    except Exception as e:
        log.warning("[USERBOT] Falha na recuperação de mensagens perdidas: %s", e)

    return True
