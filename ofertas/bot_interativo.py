"""Bot do Telegram: posta os ciclos automáticos e, no privado, converte
qualquer link colado (ML/Shopee/Amazon) em post com o seu link de afiliado.
"""
import asyncio
import logging
import secrets

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)

from . import db, pipeline
from .config import config
from .grok import grok_service
from .models import Oferta
from .sources import detectar_fonte
from .telegram_poster import postar_oferta
from .utils import extrair_urls

log = logging.getLogger("ofertas.bot")

_pendentes: dict[str, Oferta] = {}


async def _cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot de ofertas no ar!\n\n"
        "• Cole aqui um link do Mercado Livre, Shopee, Amazon ou AliExpress e eu preparo o post "
        "com o seu link de afiliado.\n"
        "• /id — mostra o id deste chat (ou do canal, se você encaminhar um post dele)\n"
        "• /fontes — lista canais e grupos monitorados como fonte\n"
        "• /addfonte <chat_id> <nome> — adiciona um canal/grupo para monitoramento\n"
        "• /delfonte <chat_id> — remove um canal/grupo monitorado\n"
        "• /ciclo — roda uma busca de ofertas agora\n"
        "• /status — situação do bot"
    )


async def _cmd_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        f"Este chat: `{update.effective_chat.id}`\n"
        f"Seu user id: `{update.effective_user.id}`\n\n"
        "Para descobrir o id do canal, encaminhe aqui qualquer post dele.",
        parse_mode="Markdown",
    )


async def _cmd_fontes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _e_dono(update):
        return
    fontes = db.listar_fontes_telegram()
    if not fontes:
        await update.message.reply_text(
            "📢 Nenhuma fonte do Telegram cadastrada ainda.\n\n"
            "Use `/addfonte <id_do_canal> <nome>` ou configure no painel para monitorar grupos/canais automaticamente.",
            parse_mode="Markdown",
        )
        return
    linhas = ["📢 *Fontes do Telegram monitoradas:*", ""]
    for f in fontes:
        st = "🟢 Ativa" if f.get("ativa") else "🔴 Inativa"
        linhas.append(f"• *{f.get('nome')}* (`{f.get('chat_id')}`) — {st}")
        if f.get("ultimo_processamento"):
            linhas.append(f"  Última msg ID: `{f.get('ultima_msg_id')}` em {f.get('ultimo_processamento')}")
    await update.message.reply_text("\n".join(linhas), parse_mode="Markdown")


async def _cmd_add_fonte(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _e_dono(update):
        return
    args = ctx.args or []
    if not args:
        await update.message.reply_text("Uso: `/addfonte <id_do_chat> <nome_da_fonte>`", parse_mode="Markdown")
        return
    chat_id = args[0]
    nome = " ".join(args[1:]) if len(args) > 1 else f"Canal {chat_id}"
    db.salvar_fonte_telegram(chat_id, nome, tipo="canal", ativa=True)
    await update.message.reply_text(f"✅ Fonte *{nome}* (`{chat_id}`) cadastrada e ativada com sucesso!", parse_mode="Markdown")


async def _cmd_del_fonte(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _e_dono(update):
        return
    args = ctx.args or []
    if not args:
        await update.message.reply_text("Uso: `/delfonte <id_do_chat>`", parse_mode="Markdown")
        return
    chat_id = args[0]
    db.remover_fonte_telegram(chat_id)
    await update.message.reply_text(f"🗑 Fonte `{chat_id}` removida com sucesso.", parse_mode="Markdown")


async def _cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    fontes = [nome for nome, f in (("Mercado Livre", config.fonte_ml),
                                   ("Shopee", config.fonte_shopee),
                                   ("Amazon", config.fonte_amazon),
                                   ("AliExpress", config.fonte_aliexpress)) if f.get("ativa")]
    await update.message.reply_text(
        f"📊 {db.total_postadas()} ofertas postadas até agora\n"
        f"🔎 Fontes automáticas: {', '.join(fontes) or 'nenhuma'}\n"
        f"⏱ Ciclo a cada {config.intervalo_minutos} min, "
        f"máx. {config.max_posts_por_ciclo} posts por ciclo\n"
        f"🎯 Desconto mínimo: {config.desconto_minimo}%"
    )


def _e_dono(update: Update) -> bool:
    return bool(config.owner_id) and update.effective_user.id == config.owner_id


async def _cmd_ciclo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _e_dono(update):
        return
    await update.message.reply_text("🔄 Rodando um ciclo de busca...")
    postadas = await pipeline.executar_ciclo(ctx.bot)
    await update.message.reply_text(f"✅ Ciclo terminou: {postadas} oferta(s) postada(s).")


async def _receber_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not config.owner_id:
        await update.message.reply_text(
            "⚠️ Defina TELEGRAM_OWNER_ID no .env para usar o conversor.\n"
            f"Seu user id é `{update.effective_user.id}`.", parse_mode="Markdown")
        return
    if not _e_dono(update):
        return

    msg = update.effective_message
    urls = extrair_urls(msg.text or msg.caption or "")
    fonte = url = None
    for u in urls:
        fonte = detectar_fonte(u)
        if fonte:
            url = u
            break
    if not fonte:
        await update.message.reply_text("Não reconheci nenhum link de ML, Shopee, Amazon ou AliExpress aí. 🤔")
        return

    aviso = await update.message.reply_text("🔎 Convertendo, um instante...")
    try:
        oferta = await asyncio.to_thread(fonte.converter, url)
        if grok_service.ativo:
            texto_contexto = msg.text or msg.caption or ""
            oferta = await asyncio.to_thread(grok_service.otimizar_oferta, oferta, texto_contexto)
    except Exception as e:
        await aviso.edit_text(f"❌ Não consegui converter: {e}")
        return
    await aviso.delete()

    token = secrets.token_hex(4)
    _pendentes[token] = oferta
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Pegar oferta", url=oferta.url_afiliado)],
        [InlineKeyboardButton("✅ Postar no canal", callback_data=f"post:{token}"),
         InlineKeyboardButton("🗑 Descartar", callback_data=f"drop:{token}")],
    ])
    await postar_oferta(ctx.bot, oferta, update.effective_chat.id, teclado=teclado)


async def _receber_forward(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    texto = msg.text or msg.caption or ""
    if any(detectar_fonte(u) for u in extrair_urls(texto)):
        await _receber_link(update, ctx)  # encaminhou uma oferta -> converte normalmente
        return
    origem = getattr(msg, "forward_origin", None)
    chat_origem = getattr(origem, "chat", None)
    if chat_origem:
        await msg.reply_text(
            f"📢 Id desse canal/grupo: `{chat_origem.id}`\n"
            "É o valor de TELEGRAM_CHAT_ID no .env.",
            parse_mode="Markdown",
        )
    else:
        await msg.reply_text(
            "Não consegui ver de onde veio — encaminhe direto do canal, sem intermediários."
        )


async def _receber_mensagem_canal_grupo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post or update.message
    if not msg:
        return

    chat = update.effective_chat
    if not chat:
        return

    source_id = str(chat.id)
    dest_id = str(config.chat_id).strip()

    # Anti-loop: nunca processar publicações do próprio canal de destino
    if dest_id and (source_id == dest_id or source_id == dest_id.lstrip("-100")):
        return

    # Anti-loop: se o autor da mensagem for o próprio bot
    if msg.from_user and ctx.bot and msg.from_user.id == ctx.bot.id:
        return

    # Verifica se a fonte está cadastrada e ativa
    fontes_ativas = {str(f["chat_id"]): f for f in db.listar_fontes_telegram() if f.get("ativa")}
    fontes_cfg = {str(c) for c in (config.fonte_telegram.get("canais") or [])}

    # Se há fontes cadastradas/configuradas, restringe a elas
    if fontes_ativas or fontes_cfg:
        if source_id not in fontes_ativas and source_id not in fontes_cfg:
            return

    texto = msg.text or msg.caption or ""
    if not texto:
        return

    imagem_url = None
    if msg.photo:
        imagem_url = msg.photo[-1].file_id

    try:
        await pipeline.processar_mensagem_telegram(
            texto=texto,
            imagem_url=imagem_url,
            source_id=source_id,
            message_id=msg.message_id,
            bot=ctx.bot,
            dry_run=bool(config.fonte_telegram.get("dry_run", False)),
        )
    except Exception as e:
        log.error("[SCRAPER] Erro ao processar postagem de canal/grupo %s: %s", source_id, e)


async def _callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    acao, _, token = q.data.partition(":")
    oferta = _pendentes.pop(token, None)

    async def _status(texto: str):
        if q.message.photo:
            await q.edit_message_caption((q.message.caption or "") + f"\n\n{texto}")
        else:
            await q.edit_message_text((q.message.text or "") + f"\n\n{texto}")

    if not oferta:
        await _status("⚠️ Essa prévia expirou — mande o link de novo.")
        return
    if acao == "post":
        await postar_oferta(ctx.bot, oferta, config.chat_id)
        db.registrar(oferta)
        await _status("✅ Postada no canal!")
    else:
        await _status("🗑 Descartada.")


async def _job_ciclo(ctx: ContextTypes.DEFAULT_TYPE):
    try:
        await pipeline.executar_ciclo(ctx.bot)
    except Exception as e:
        log.exception("Ciclo automático falhou")
        await pipeline.avisar_dono(ctx.bot, f"⚠️ O ciclo automático falhou: {type(e).__name__}: {e}")


async def _post_init(app: Application) -> None:
    """Hook executado após a inicialização do Application para conectar o Telethon Userbot."""
    try:
        from .sources import telegram_userbot
        if telegram_userbot.tem_credenciais() and telegram_userbot.tem_sessao_salva():
            log.info("Iniciando Telegram Userbot (Telethon) para monitorar canais de terceiros...")
            await telegram_userbot.iniciar_userbot(app.bot)
        else:
            log.info("Telegram Userbot não iniciado (sem credenciais ou sem sessão logada).")
    except Exception as e:
        log.warning("Não foi possível iniciar o Telethon Userbot: %s", e)


def rodar():
    if not config.bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN não configurado — veja o README (passo 1).")

    app = Application.builder().token(config.bot_token).post_init(_post_init).build()
    app.add_handler(CommandHandler("start", _cmd_start))
    app.add_handler(CommandHandler("id", _cmd_id))
    app.add_handler(CommandHandler("status", _cmd_status))
    app.add_handler(CommandHandler("fontes", _cmd_fontes))
    app.add_handler(CommandHandler("addfonte", _cmd_add_fonte))
    app.add_handler(CommandHandler("delfonte", _cmd_del_fonte))
    app.add_handler(CommandHandler("ciclo", _cmd_ciclo))
    app.add_handler(CallbackQueryHandler(_callback))
    app.add_handler(MessageHandler(filters.FORWARDED & filters.ChatType.PRIVATE, _receber_forward))
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.CAPTION) & filters.ChatType.PRIVATE & ~filters.COMMAND,
        _receber_link))
    app.add_handler(MessageHandler(
        (filters.ChatType.CHANNEL | filters.ChatType.GROUPS) & (filters.TEXT | filters.CAPTION | filters.PHOTO),
        _receber_mensagem_canal_grupo))

    tem_fonte = any(f.get("ativa") for f in
                    (config.fonte_ml, config.fonte_shopee, config.fonte_amazon, config.fonte_aliexpress, config.fonte_telegram))
    if tem_fonte and config.intervalo_minutos > 0 and config.chat_id:
        app.job_queue.run_repeating(_job_ciclo, interval=config.intervalo_minutos * 60, first=30)
        log.info("Ciclo automático a cada %d min", config.intervalo_minutos)
    else:
        log.info("Ciclo automático desligado (sem fonte ativa ou sem CHAT_ID)")

    log.info("Bot rodando — monitorando mensagens e privado do Telegram")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
