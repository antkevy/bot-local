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
    chats_monitorados = [f["chat_id"] for f in fontes_db]

    # Handler de novas mensagens
    @client.on(events.NewMessage)
    async def _ao_receber_mensagem(event: events.NewMessage.Event):
        try:
            chat = await event.get_chat()
            chat_id = getattr(chat, "id", None) or event.chat_id
            username = getattr(chat, "username", None) or ""
            chat_str = str(chat_id)
            username_str = f"@{username.lower()}" if username else ""

            # Verificar se este chat/canal está na lista de fontes ativas
            fontes_atuais = db.listar_fontes_telegram(ativas_apenas=True)
            ids_ativas = {str(f["chat_id"]).strip().lower() for f in fontes_atuais}

            # Se o chat estiver cadastrado por ID ou por @username
            chat_autorizado = (
                chat_str in ids_ativas
                or chat_str.lstrip("-100") in ids_ativas
                or (username_str and username_str in ids_ativas)
            )

            if not chat_autorizado:
                return

            texto = event.raw_text or event.message.message or ""
            if not texto:
                return

            # Anti-Loop: Não processar se for o próprio canal de destino do bot
            if e_postagem_propria(chat_id, destination_chat_id=config.chat_id):
                log.debug("[USERBOT] Ignorando mensagem originada no próprio canal de destino: %s", chat_id)
                return

            log.info("[USERBOT] Nova mensagem capturada do canal/grupo %s (ID: %s, Msg: %s)", getattr(chat, "title", username), chat_id, event.id)

            # Atualizar status da fonte
            db.atualizar_status_fonte_telegram(chat_str, event.id)

            # Enviar para o pipeline central
            resultado = await pipeline.processar_mensagem_telegram(
                texto=texto,
                imagem_url=None,
                source_id=chat_str,
                message_id=event.id,
                bot=bot_poster,
                dry_run=dry_run,
            )

            if resultado.get("ok"):
                log.info("[USERBOT] ✅ Oferta da fonte %s processada com sucesso!", chat_str)
            else:
                log.info("[USERBOT] ℹ️ Mensagem da fonte %s não publicada: %s", chat_str, resultado.get("motivo"))

        except Exception as e:
            log.error("[USERBOT] Erro ao processar mensagem do evento Telethon: %s", e)

    log.info("[USERBOT] Monitorando %d fontes ativas do Telegram em tempo real.", len(chats_monitorados))
    return True
