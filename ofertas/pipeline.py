import asyncio
import logging
import re

from telegram import Bot

from . import db
from .config import config, dentro_do_horario
from .grok import grok_service
from .models import Oferta
from .sources import aliexpress, amazon, mercadolivre, shopee
from .telegram_poster import postar_oferta

log = logging.getLogger("ofertas.pipeline")


def coletar() -> list[Oferta]:
    """Busca ofertas nas fontes automáticas ativas (sem link de afiliado ainda, no caso do ML)."""
    todas: list[Oferta] = []

    if config.fonte_shopee.get("ativa"):
        if config.shopee_app_id and config.shopee_app_secret:
            try:
                todas += shopee.buscar_ofertas(int(config.fonte_shopee.get("limite", 30)))
            except Exception as e:
                log.error("Shopee: %s", e)
        else:
            log.warning("Shopee ativa no config.yaml mas sem credenciais no .env — pulando")

    if config.fonte_amazon.get("ativa"):
        if config.amazon_tag:
            try:
                todas += amazon.buscar_ofertas()
            except Exception as e:
                log.error("Amazon: %s", e)
        else:
            log.warning("Amazon ativa no config.yaml mas sem AMAZON_TAG no .env — pulando")

    if config.fonte_ml.get("ativa"):
        if mercadolivre.tem_sessao():
            try:
                todas += mercadolivre.buscar_ofertas()
            except Exception as e:
                log.error("Mercado Livre: %s", e)
        else:
            log.warning("Mercado Livre ativo mas sem sessão de afiliado — rode: uv run python -m ofertas ml-login")

    if config.fonte_aliexpress.get("ativa"):
        if config.aliexpress_app_key and config.aliexpress_app_secret:
            try:
                todas += aliexpress.buscar_ofertas(int(config.fonte_aliexpress.get("limite", 30)))
            except Exception as e:
                log.error("AliExpress: %s", e)
        else:
            log.warning("AliExpress ativo no config.yaml mas sem credenciais no .env — pulando")

    return todas


def filtrar(ofertas: list[Oferta]) -> list[Oferta]:
    aprovadas = []
    for o in ofertas:
        if not o.titulo:
            continue
        if db.ja_postada(o.uid, config.nao_repetir_dias):
            continue
        if config.desconto_minimo and (o.desconto or 0) < config.desconto_minimo:
            continue
        if o.preco is not None:
            if config.preco_minimo and o.preco < config.preco_minimo:
                continue
            if config.preco_maximo and o.preco > config.preco_maximo:
                continue
        titulo = o.titulo.lower()
        if any(p in titulo for p in config.palavras_bloqueadas):
            continue
        aprovadas.append(o)
    return aprovadas


def _chave_similar(titulo: str) -> str:
    """Variações do mesmo produto (cor, tamanho) costumam repetir as primeiras palavras."""
    return " ".join(re.findall(r"\w+", titulo.lower())[:5])


def escolher(ofertas: list[Oferta], n: int) -> list[Oferta]:
    """Top N por desconto, alternando plataformas e pulando variações do mesmo produto."""
    filas: dict[str, list[Oferta]] = {}
    for o in sorted(ofertas, key=lambda o: o.desconto or 0, reverse=True):
        filas.setdefault(o.plataforma, []).append(o)
    ordem = sorted(filas.values(), key=lambda f: f[0].desconto or 0, reverse=True)
    escolhidas: list[Oferta] = []
    vistas: set[str] = set()
    while len(escolhidas) < n and any(ordem):
        for fila in ordem:
            while fila:
                o = fila.pop(0)
                chave = _chave_similar(o.titulo)
                if chave not in vistas:
                    vistas.add(chave)
                    escolhidas.append(o)
                    break
            if len(escolhidas) >= n:
                break
    return escolhidas


async def avisar_dono(bot: Bot, texto: str) -> None:
    """Manda um aviso no privado do dono (se configurado) — para operação sem supervisão."""
    if not config.owner_id:
        return
    try:
        await bot.send_message(config.owner_id, texto)
    except Exception as e:
        log.warning("Não consegui avisar o dono: %s", e)


async def executar_ciclo(bot: Bot) -> int:
    """Um ciclo completo: coletar -> filtrar -> escolher -> gerar links -> postar. Retorna nº de posts."""
    if not dentro_do_horario():
        log.info("Fora do horário ativo (%s) — ciclo pulado", config.horario_ativo)
        return 0

    brutas = await asyncio.to_thread(coletar)
    boas = filtrar(brutas)
    escolhidas = escolher(boas, config.max_posts_por_ciclo)

    # Mercado Livre: gerar link de afiliado só das escolhidas (linkbuilder é caro)
    ml_pendentes = [o for o in escolhidas if o.plataforma == "mercadolivre" and not o.url_afiliado]
    if ml_pendentes:
        try:
            await asyncio.to_thread(mercadolivre.gerar_links_afiliado, ml_pendentes, bot)
        except Exception as e:
            log.error("Geração de afiliados ML falhou: %s", e)

    postadas = 0
    for o in escolhidas:
        if not o.url_afiliado:
            log.warning("Sem link de afiliado, pulando: %s", o.titulo[:60])
            continue

        # Camada de inteligência e normalização com Grok
        if grok_service.ativo:
            try:
                await asyncio.to_thread(grok_service.otimizar_oferta, o)
            except Exception as e:
                log.warning("[GROK] Falha ao otimizar oferta '%s': %s", o.titulo[:40], e)

        if o.tipo == "irrelevante":
            log.info("[GROK] Oferta classificada como irrelevante, pulando: %s", o.titulo[:60])
            continue

        try:
            await postar_oferta(bot, o, config.chat_id)
        except Exception as e:
            log.error("Falha ao postar '%s': %s", o.titulo[:60], e)
            continue
        db.registrar(o)
        postadas += 1
        if o is not escolhidas[-1]:
            await asyncio.sleep(config.espacamento_segundos)

    log.info("Ciclo: %d coletadas, %d aprovadas, %d postadas", len(brutas), len(boas), postadas)
    return postadas


async def processar_mensagem_telegram(
    texto: str,
    imagem_url: str | None = None,
    source_id: str | int = 0,
    message_id: int = 0,
    bot: Bot | None = None,
    dry_run: bool = False,
) -> dict:
    """Processa uma mensagem capturada de canal/grupo do Telegram pelo pipeline central do bot."""
    from .sources import detectar_fonte, telegram_scraper

    log.info("[SCRAPER] Nova mensagem recebida (fonte=%s, msg_id=%s)", source_id, message_id)

    # 1. Anti-loop: nunca capturar publicações do próprio canal de destino
    if telegram_scraper.e_postagem_propria(source_id, destination_chat_id=config.chat_id):
        log.info("[SCRAPER] Mensagem ignorada: originada do próprio canal de destino (%s)", source_id)
        return {"ok": False, "motivo": "origem_canal_destino"}

    # 2. Deduplicação: se a mensagem já foi processada anteriormente
    if source_id and message_id and db.ja_processada_msg_telegram(source_id, message_id):
        log.info("[SCRAPER] Mensagem duplicada ignorada (fonte=%s, msg_id=%s)", source_id, message_id)
        return {"ok": False, "motivo": "duplicada"}

    # 3. Pré-processamento
    pre = telegram_scraper.pre_processar_mensagem(texto)
    links_mp = pre["links_marketplace"]

    oferta: Oferta | None = None

    if links_mp:
        primeiro = links_mp[0]
        url = primeiro["url"]
        fonte_mod = primeiro["fonte"]
        try:
            oferta = await asyncio.to_thread(fonte_mod.converter, url)
        except Exception as e:
            log.warning("[SCRAPER] Erro ao converter produto do link '%s': %s", url, e)

    # 4. Inteligência e Classificação com Grok
    log.info("[AI] Classificando mensagem...")
    titulo_base = oferta.titulo if oferta else ""
    try:
        resultado_ia = await asyncio.to_thread(grok_service.analisar_texto, texto, titulo_base=titulo_base)
    except Exception as e:
        log.warning("[AI] Falha ao analisar mensagem com IA (fallback ativado): %s", e)
        from .grok import GrokResult
        resultado_ia = GrokResult(
            tipo="produto" if oferta else "irrelevante",
            titulo_otimizado=titulo_base,
            tem_cupom=bool(pre.get("cupons_candidatos")),
            cupom=pre.get("cupons_candidatos", [None])[0] if pre.get("cupons_candidatos") else None,
            beneficio_cupom=None,
            confianca=0.5,
        )

    log.info(
        "[AI] Tipo: %s, Confiança: %.2f, Cupom: %s",
        resultado_ia.tipo,
        resultado_ia.confianca,
        resultado_ia.cupom,
    )

    if resultado_ia.tipo == "irrelevante":
        log.info("[AI] Mensagem classificada como irrelevante. Ignorando.")
        if source_id and message_id:
            db.registrar_msg_telegram(source_id, message_id, status="irrelevante")
        return {"ok": False, "motivo": "irrelevante"}

    # Se identificou produto através do scraper
    if oferta:
        if resultado_ia.titulo_otimizado:
            log.info("[AI] Título otimizado: %s", resultado_ia.titulo_otimizado)
            oferta.titulo = resultado_ia.titulo_otimizado
        if resultado_ia.tem_cupom and resultado_ia.cupom:
            oferta.cupom = resultado_ia.cupom
            oferta.beneficio_cupom = resultado_ia.beneficio_cupom
        oferta.tipo = resultado_ia.tipo
        if imagem_url and not oferta.imagem:
            oferta.imagem = imagem_url
    else:
        # Se for cupom ou promoção sem produto explícito mas com link de loja
        if resultado_ia.tipo in ("cupom", "promocao", "frete_gratis") and pre["urls"]:
            url_geral = pre["urls"][0]
            fonte_det = detectar_fonte(url_geral)
            if fonte_det:
                try:
                    oferta = await asyncio.to_thread(fonte_det.converter, url_geral)
                    if oferta:
                        oferta.tipo = resultado_ia.tipo
                        if resultado_ia.cupom:
                            oferta.cupom = resultado_ia.cupom
                            oferta.beneficio_cupom = resultado_ia.beneficio_cupom
                except Exception as e:
                    log.warning("[SCRAPER] Erro ao converter URL geral '%s': %s", url_geral, e)

    if not oferta:
        log.info("[SCRAPER] Nenhum produto ou oferta conversível encontrado na mensagem. Ignorando.")
        if source_id and message_id:
            db.registrar_msg_telegram(source_id, message_id, status="sem_produto")
        return {"ok": False, "motivo": "sem_produto"}

    # 5. Mercado Livre: se precisa de link de afiliado
    if oferta.plataforma == "mercadolivre" and not oferta.url_afiliado:
        try:
            await asyncio.to_thread(mercadolivre.gerar_links_afiliado, [oferta], bot)
        except Exception as e:
            log.error("[AFFILIATE] Geração de link ML falhou: %s", e)

    # 6. VALIDAÇÃO OBRIGATÓRIA DE AFILIADO:
    # "Se não existir link afiliado válido: NÃO publicar. NUNCA utilizar a URL original como fallback de affiliate_link."
    if not oferta.url_afiliado:
        log.warning("[AFFILIATE] Não foi possível gerar um link de afiliado para esta oferta. A publicação foi ignorada.")
        if source_id and message_id:
            db.registrar_msg_telegram(source_id, message_id, oferta.uid, status="sem_afiliado")
        return {"ok": False, "motivo": "sem_link_afiliado"}

    log.info("[AFFILIATE] Marketplace: %s, Link afiliado gerado: %s", oferta.plataforma, oferta.url_afiliado[:50])

    # 7. Filtros existentes
    aprovadas = filtrar([oferta])
    if not aprovadas:
        log.info("[FILTROS] Oferta '%s' rejeitada pelos filtros existentes.", oferta.titulo[:50])
        if source_id and message_id:
            db.registrar_msg_telegram(source_id, message_id, oferta.uid, status="filtrada")
        return {"ok": False, "motivo": "filtrada"}

    # 8. Publicação (respeitando dry_run e canal de destino)
    if dry_run or not config.chat_id or not bot:
        log.info("[PUBLISH] [DRY-RUN] Oferta pronta para publicação (chat=%s): %s", config.chat_id, oferta.titulo[:50])
        if source_id and message_id:
            db.registrar_msg_telegram(source_id, message_id, oferta.uid, status="dry_run")
        return {"ok": True, "dry_run": True, "oferta": oferta}

    try:
        log.info("[PUBLISH] Publicando oferta no canal %s: %s", config.chat_id, oferta.titulo[:50])
        await postar_oferta(bot, oferta, config.chat_id)
        db.registrar(oferta)
        if source_id and message_id:
            db.registrar_msg_telegram(source_id, message_id, oferta.uid, status="publicada")
        return {"ok": True, "oferta": oferta}
    except Exception as e:
        log.error("[PUBLISH] Falha ao publicar oferta: %s", e)
        if source_id and message_id:
            db.registrar_msg_telegram(source_id, message_id, oferta.uid, status=f"erro: {e}")
        return {"ok": False, "motivo": f"erro_envio: {e}"}
