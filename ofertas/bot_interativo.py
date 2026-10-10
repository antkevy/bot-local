"""Bot do Telegram: posta os ciclos automáticos e, no privado, converte
qualquer link colado (ML/Shopee/Amazon) em post com o seu link de afiliado.
"""
import asyncio
import logging
import re
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

# Ações aceitas no callback das prévias (data="acao:token"). Qualquer outra
# coisa é rejeitada ANTES de consumir o token — nunca vira "post" nem "drop".
_ACOES_CALLBACK = ("post", "drop")

# Formato aceito para fonte de scraping: id numérico (canal/grupo, ex.
# -1001234567890) ou @username público. O resto (aspas, tags, espaços) é
# rejeitado na escrita — defesa em profundidade, já que o painel interpola
# esse valor em markup/atributos.
_RE_FONTE_VALIDA = re.compile(r"^-?\d+$|^@[A-Za-z0-9_]{3,32}$")


def _chat_id_valido(chat_id: str) -> bool:
    """Diz se um chat_id (já normalizado) tem formato seguro de fonte."""
    return bool(chat_id) and bool(_RE_FONTE_VALIDA.fullmatch(chat_id))


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
    from .sources.telegram_scraper import normalizar_username_telegram
    # Normaliza (id/@username/t.me) e valida o formato ANTES de gravar: o valor
    # vai parar no painel e em mensagens, então nada de aspas/tags entrando cru.
    chat_id = normalizar_username_telegram(args[0])
    if not _chat_id_valido(chat_id):
        await update.message.reply_text(
            "❌ Formato inválido. Use o id do chat (ex.: `-1001234567890`), "
            "`@username` ou link `t.me/...` do canal/grupo.",
            parse_mode="Markdown",
        )
        return
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


async def _cmd_status_ml(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _e_dono(update):
        return
    from .sources.ml_auth import ml_auth_service
    res = ml_auth_service.testar_autenticacao()
    if res.get("authenticated"):
        metodo = "Link Builder" if res.get("method") == "linkbuilder" else "Cookie"
        await update.message.reply_text(f"✅ Mercado Livre: *Autenticado via {metodo}*\nLink de teste gerado: `{res.get('link_teste', '')}`", parse_mode="Markdown")
    else:
        await update.message.reply_text(
            "⚠️ Mercado Livre: *Autenticação Necessária*\n"
            "Nem o Link Builder nem o Cookie estão funcionando.\n"
            "Envie `/setcookie <seu_cookie>` para atualizar via cookie ou faça login no Link Builder.",
            parse_mode="Markdown"
        )


async def _cmd_setcookie(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _e_dono(update):
        return
    # Cookie pode vir como argumento (/setcookie ...) ou no texto da mensagem
    texto = update.message.text or ""
    partes = texto.split(maxsplit=1)
    if len(partes) < 2:
        await update.message.reply_text(
            "🍪 *Como atualizar o Cookie do Mercado Livre:*\n\n"
            "Envie o comando:\n`/setcookie <cole_seu_cookie_aqui>`\n\n"
            "_O bot testará a autenticação antes de salvar. Se for válido, reprocessará as ofertas pendentes._",
            parse_mode="Markdown"
        )
        return

    cookie_candidato = partes[1].strip()
    await update.message.reply_text("⏳ Validando novo cookie do Mercado Livre com teste real...")

    from .sources.ml_auth import ml_auth_service
    resultado = ml_auth_service.validar_e_salvar_novo_cookie(cookie_candidato, bot=ctx.bot)

    if resultado.get("ok"):
        ofertas_rep = resultado.get("ofertas_reprocessadas", 0)
        msg_rep = f"\n🔄 {ofertas_rep} oferta(s) pendente(s) reprocessada(s)!" if ofertas_rep else ""
        await update.message.reply_text(
            f"✅ *Novo cookie do Mercado Livre validado e salvo com sucesso!*{msg_rep}",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"❌ *{resultado.get('erro', 'Falha ao validar cookie')}*\n_O cookie anterior foi mantido._",
            parse_mode="Markdown"
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


def _e_mesmo_canal(source_id: str, dest_id: str) -> bool:
    """Diz se dois ids de chat são o mesmo canal, em qualquer das formas.

    O Telegram representa um canal de três jeitos: -1001234..., 1234..., e
    -1001234... de novo. Comparar as duas pontas exige tomar o prefixo como
    prefixo. `lstrip("-100")` não serve: ele apaga o CONJUNTO {'-','1','0'}
    do começo da string, então num canal -1001... comia dígitos do id e a
    comparação deixava de valer — o anti-loop deixava de segurar.
    """
    if not source_id or not dest_id:
        return False
    curto = dest_id.removeprefix("-100")
    return source_id in (dest_id, curto, "-100" + curto)


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
    if _e_mesmo_canal(source_id, dest_id):
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
    try:
        await q.answer()
    except Exception as e:
        # O handler não pode cair só porque o Telegram não aceitou o answer.
        log.warning("[CALLBACK] Erro ao responder o answer: %s", e)

    acao, _, token = (q.data or "").partition(":")
    if acao not in _ACOES_CALLBACK:
        # Ação desconhecida (dado adulterado/fora de catálogo): NÃO consome o
        # token — a prévia continua válida — e não responde como "descartada",
        # que seria o mesmo que silenciar um descarte indevido.
        log.warning("[CALLBACK] Ação não reconhecida no callback: %r", acao)
        await _editar_previa(q, "⚠️ Ação não reconhecida.")
        return

    oferta = _pendentes.pop(token, None)

    if not oferta:
        await _editar_previa(q, "⚠️ Essa prévia expirou — mande o link de novo.")
        return

    try:
        if acao == "post":
            await postar_oferta(ctx.bot, oferta, config.chat_id)
            db.registrar(oferta)
            await _editar_previa(q, "✅ Postada no canal!")
        else:
            await _editar_previa(q, "🗑 Descartada.")
    except Exception as e:
        # Falha ao publicar (rede, Telegram) não pode derrubar o handler sem
        # deixar o dono saber o que houve com a prévia.
        log.exception("[CALLBACK] Falha ao processar ação %s", acao)
        await _editar_previa(q, f"❌ Erro ao processar: {e}")


async def _editar_previa(q, texto: str):
    """Acrescenta um status à prévia, foto ou texto, sem derrubar o handler."""
    try:
        msg = q.message
        if not msg:
            return
        if msg.photo:
            await q.edit_message_caption((msg.caption or "") + f"\n\n{texto}")
        else:
            await q.edit_message_text((msg.text or "") + f"\n\n{texto}")
    except Exception as e:
        log.warning("[CALLBACK] Erro ao editar a prévia: %s", e)


async def _job_ciclo(ctx: ContextTypes.DEFAULT_TYPE):
    try:
        await pipeline.executar_ciclo(ctx.bot)
    except Exception as e:
        log.exception("Ciclo automático falhou")
        await pipeline.avisar_dono(ctx.bot, f"⚠️ O ciclo automático falhou: {type(e).__name__}: {e}")


# ── Ativação automática do userbot ───────────────────────────────────
# O login acontece pelo painel (sem SSH). Entre o login e o monitor subir
# não pode haver comando de terminal: o job abaixo checa a sessão a cada 60s,
# sobe o monitor quando ela aparece (≤ 60s depois do login) e se cancela
# sozinho. Sem ele, um login bem-sucedido ficaria órfão até um restart.
JOB_USERBOT_NOME = "userbot_ativacao"
JOB_USERBOT_INTERVALO = 60   # segundos
JOB_USERBOT_PRIMEIRO = 10    # primeira checagem, segundos após o boot


def _parar_job_userbot(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        for job in ctx.application.job_queue.get_jobs_by_name(JOB_USERBOT_NOME):
            job.schedule_removal()
    except Exception as e:
        log.warning("[USERBOT] Não consegui cancelar o job de ativação: %s", e)


async def _job_userbot(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """De prontidão até a sessão existir; depois sobe o monitor e se cancela."""
    from .sources import telegram_userbot as tb
    try:
        if tb.userbot_ativo():
            log.info("[USERBOT] Monitor já ativo; desligando o job de ativação.")
            _parar_job_userbot(ctx)
            return
        if not tb.tem_sessao_salva():
            # Ainda sem sessão — o login pelo painel pode acontecer a qualquer
            # momento. Sem log aqui: não é um barulho por minuto.
            return
        if await tb.iniciar_userbot(ctx.bot):
            log.info("[USERBOT] Monitor iniciado pelo job de ativação; desligando o job.")
            _parar_job_userbot(ctx)
    except Exception as e:
        log.warning("[USERBOT] Job de ativação falhou: %s", e)


async def _post_init(app: Application) -> None:
    """Agenda o job que liga o userbot assim que uma sessão existir.

    A sessão é criada pelo login no painel. Se as credenciais ainda não
    existirem, não há o que agendar (e o painel não tem com o que logar).
    """
    from .sources import telegram_userbot as tb
    if not tb.tem_credenciais():
        log.info("Telegram Userbot desligado (sem TELEGRAM_API_ID/HASH no .env).")
        return
    fila = getattr(app, "job_queue", None)
    if fila is None:
        log.warning("Telegram Userbot: sem JobQueue no Application; ativação automática desligada.")
        return
    fila.run_repeating(
        _job_userbot,
        interval=JOB_USERBOT_INTERVALO,
        first=JOB_USERBOT_PRIMEIRO,
        name=JOB_USERBOT_NOME,
    )
    log.info("Telegram Userbot: job de ativação agendado (checa a sessão a cada %d s).",
             JOB_USERBOT_INTERVALO)


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
    app.add_handler(CommandHandler("setcookie", _cmd_setcookie))
    app.add_handler(CommandHandler("statusml", _cmd_status_ml))
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

    # `stop_signals=None` tira os handlers do PTB: ele levantaria SystemExit
    # sem avisar a thread da coleta, e o interpretador ficaria esperando ela
    # em vez de sair. O nosso handler pede a parada ANTES, então o ciclo
    # cede na primeira checagem e o processo encerra em segundos.
    from . import parada
    parada.instalar_handlers(parada.pedir)

    app.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None)
