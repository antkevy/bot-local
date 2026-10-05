import asyncio
import logging
import re

from telegram import Bot

from . import db
from .config import config, dentro_do_horario
from .filters import passes_product_filters
from .formatter import _preco_util
from .grok import grok_service
from .models import Oferta, tipo_principal, tokens_conteudo
from .parada import limpar as limpar_parada, pedido as parada_pedida, pedir as pedir_parada
from .publishing_control import publishing_controller
from .sources import aliexpress, amazon, mercadolivre, shopee
from .telegram_poster import postar_oferta

log = logging.getLogger("ofertas.pipeline")


def coletar() -> list[Oferta]:
    """Busca ofertas nas fontes automáticas ativas (sem link de afiliado ainda, no caso do ML).

    Só a fonte ativa no config entra. Roda numa thread (`executar_ciclo` usa
    `asyncio.to_thread`), então precisa consultar `parada.pedido()` para ceder
    rápido quando o serviço está encerrando: o `SystemExit` do PTB já soltou a
    thread principal, e o interpretador só sai quando ESTA thread acabar.
    """
    todas: list[Oferta] = []

    def _parou(qual: str) -> bool:
        if parada_pedida():
            log.info("Coleta interrompida antes de %s: o processo está encerrando. "
                     "%d oferta(s) já coletadas.", qual, len(todas))
            return True
        return False

    if config.fonte_shopee.get("ativa") and not _parou("Shopee"):
        if config.shopee_app_id and config.shopee_app_secret:
            try:
                todas += shopee.buscar_ofertas(int(config.fonte_shopee.get("limite", 30)))
            except Exception as e:
                log.error("Shopee: %s", e)
        else:
            log.warning("Shopee ativa no config.yaml mas sem credenciais no .env — pulando")

    if config.fonte_amazon.get("ativa") and not _parou("Amazon"):
        if config.amazon_tag:
            try:
                todas += amazon.buscar_ofertas()
            except Exception as e:
                log.error("Amazon: %s", e)
        else:
            log.warning("Amazon ativa no config.yaml mas sem AMAZON_TAG no .env — pulando")

    if config.fonte_ml.get("ativa") and not _parou("Mercado Livre"):
        if mercadolivre.tem_sessao():
            try:
                todas += mercadolivre.buscar_ofertas()
            except Exception as e:
                log.error("Mercado Livre: %s", e)
        else:
            log.warning("Mercado Livre ativo mas sem sessão de afiliado — rode: uv run python -m ofertas ml-login")

    if config.fonte_aliexpress.get("ativa") and not _parou("AliExpress"):
        if config.aliexpress_app_key and config.aliexpress_app_secret:
            try:
                todas += aliexpress.buscar_ofertas(int(config.fonte_aliexpress.get("limite", 30)))
            except Exception as e:
                log.error("AliExpress: %s", e)
        else:
            log.warning("AliExpress ativo no config.yaml mas sem credenciais no .env — pulando")

    return todas


def _tipo_saturado(titulo: str, contagem: dict[str, int]) -> str | None:
    """Motivo se este tipo de produto já saiu vezes demais na janela, senão None."""
    tipo = tipo_principal(titulo)
    if not tipo:
        return None
    usados = contagem.get(tipo, 0)
    if usados >= db.MAX_REPETICOES_POR_TIPO:
        return (f"tipo '{tipo}' já saiu {usados}x em {config.cooldown_tipo_horas}h "
                f"(máximo {db.MAX_REPETICOES_POR_TIPO})")
    return None


def _equivalente_a_postado(titulo: str, palavras: list[frozenset[str]]) -> str | None:
    """Motivo se o título for o mesmo produto de um post recente, senão None.

    Dois títulos são o mesmo produto quando dividem ao menos duas palavras
    significativas e ao menos 1/3 delas. É o caso das variações que os
    marketplaces publicam como produtos distintos ("Bola de rolamento
    automática para filhotes" / "Bola inteligente automática recarregável").
    """
    tokens = tokens_conteudo(titulo)
    if not tokens:
        return None
    for outros in palavras:
        comum = tokens & outros
        if (len(comum) >= db.PALAVRAS_COMUNS_MINIMO
                and len(comum) * db.FRACAO_COMUM_MINIMA >= len(tokens)):
            return "mesmo produto de um post recente (" + ", ".join(sorted(comum)) + ")"
    return None


def filtrar(ofertas: list[Oferta]) -> list[Oferta]:
    """Aplica o sistema central de filtros de qualidade (estrelas, vendas, descontos, palavras bloqueadas).

    Cada oferta aprovada sai daqui **reservada** para este processo. Não é
    cosmético: entre esta função e o `db.registrar()` no fim da publicação há
    a geração de link de afiliado no navegador e a normalização com a IA, o
    que dá tempo de outro processo passar pelo mesmo `ja_postada` e postar a
    mesma oferta. Quem não conseguir a reserva simplesmente não recebe a oferta.
    """
    aprovadas = []
    # Repetição por tipo: o uid não distingue "três mochilas de fabricantes
    # diferentes", e no canal são a mesma oferta repetida. O índice é montado
    # uma vez por ciclo e atualizado com cada aprovação, para duas ofertas do
    # mesmo tipo não saírem juntas.
    palavras_postadas, contagem_tipos = db.tipos_recentes(config.cooldown_tipo_horas)
    barradas_por_tipo: list[Oferta] = []
    for o in ofertas:
        if not o.titulo:
            continue
        # Bloqueio permanente de repetido, salvo se o preço cair: um produto
        # já postado só volta ao canal com preço menor do que o gravado na
        # última postagem. (não há janela de dias — hoje o `nao_repetir_dias`
        # do config serve de referência no painel, a regra real é esta.)
        preco_antigo = db.preco_ultima_postagem(o.uid)
        if preco_antigo is not None:
            caiu = o.preco is not None and o.preco < preco_antigo
            if not caiu:
                atual = ("sem preço" if o.preco is None else f"{o.preco:.2f}")
                log.info(
                    "[FILTER] Oferta '%s' ignorada: produto já postado (R$%.2f) e preço não caiu (atual: %s) — só republica se o preço cair.",
                    o.titulo[:40], preco_antigo, atual,
                )
                continue
            log.info("[FILTER] Oferta '%s' re-aprovada: preço caiu de R$%.2f para R$%.2f.",
                     o.titulo[:40], preco_antigo, o.preco)
        ok, motivo = passes_product_filters(o)
        if not ok:
            log.info("[FILTER] Oferta '%s' rejeitada: %s", o.titulo[:40], motivo)
            continue
        # O cooldown por tipo é a última trava antes da reserva, e as barradas
        # ficam de lado: se o cooldown esvaziar o lote, elas voltam ao fim (o
        # silêncio do canal é pior que uma repetição).
        motivo_tipo = (_equivalente_a_postado(o.titulo, palavras_postadas)
                       or _tipo_saturado(o.titulo, contagem_tipos))
        if motivo_tipo:
            log.info("[FILTER] Oferta '%s' ignorada: %s.", o.titulo[:40], motivo_tipo)
            barradas_por_tipo.append(o)
            continue
        if not db.reservar(o.uid):
            log.info("[FILTER] Oferta '%s' ignorada: outro processo já está publicando ela.", o.titulo[:40])
            continue
        aprovadas.append(o)
        tokens = tokens_conteudo(o.titulo)
        if tokens:
            palavras_postadas.append(tokens)
        tipo = tipo_principal(o.titulo)
        if tipo:
            contagem_tipos[tipo] = contagem_tipos.get(tipo, 0) + 1
    if not aprovadas and barradas_por_tipo:
        log.info("[FILTER] Lote vazio: liberando %d oferta(s) barrada(s) só por repetição de tipo "
                 "(preferimos repetir a ficar mudo).", len(barradas_por_tipo))
        for o in barradas_por_tipo:
            if not db.reservar(o.uid):
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
    # Janela nova: a parada de um encerramento anterior não pode contaminar
    # este ciclo, que vai rodar horas depois.
    limpar_parada()
    if not dentro_do_horario():
        log.info("Fora do horário ativo (%s) — ciclo pulado", config.horario_ativo)
        return 0

    brutas = await asyncio.to_thread(coletar)
    if parada_pedida():
        # Chegou o SIGTERM no meio da coleta. As ofertas ficam no cache para o
        # próximo ciclo; o que não pode é sair postando com o processo em
        # Riemann de desligamento.
        log.info("Ciclo abortado a pedido de parada (%d oferta(s) coletadas). "
                 "Nada foi postado.", len(brutas))
        return 0
    boas = filtrar(brutas)
    escolhidas = escolher(boas, config.max_posts_por_ciclo)

    # `filtrar` reservou todas as aprovadas, mas só max_posts_por_ciclo serão
    # tentadas agora. As que ficaram de fora precisam voltar ao limbo, senão
    # ficariam bloqueadas até o TTL sem nunca terem sido publicadas.
    a_liberar = {o.uid for o in escolhidas}
    for o in boas:
        if o.uid not in a_liberar:
            db.liberar_reserva(o.uid)

    # Mercado Livre: gerar link de afiliado só das escolhidas (linkbuilder é caro)
    ml_pendentes = [o for o in escolhidas if o.plataforma == "mercadolivre" and not o.url_afiliado]
    if ml_pendentes:
        try:
            await asyncio.to_thread(mercadolivre.gerar_links_afiliado, ml_pendentes, bot)
        except Exception as e:
            log.error("Geração de afiliados ML falhou: %s", e)

    # AliExpress: gerar link só das escolhidas. `link.generate` tem cota da
    # Open Platform — gerar para os ~30 coletados de cada ciclo eram ~1.700
    # chamadas/dia, e quase tudo era descartado pelos filtros depois. O
    # `converter` (mensagem de canal) continua gerando na hora, por mensagem.
    for o in escolhidas:
        if o.plataforma == "aliexpress" and not o.url_afiliado:
            try:
                o.url_afiliado = await asyncio.to_thread(
                    aliexpress.gerar_link_afiliado, o.url_produto)
            except Exception as e:
                log.warning("[ALIEXPRESS] Sem link de afiliado p/ %s: %s",
                            o.id_produto, e)

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

        # Controle de Velocidade e Pausas
        pode_postar, motivo_ctrl, espera_s = publishing_controller.pode_publicar()
        if not pode_postar:
            # Só a espera de intervalo mínimo entre posts vale ser aguardada
            # dentro do próprio ciclo: ela é curta e tem teto conhecido (o
            # próprio intervalo configurado). Pausa de bloco, limite de
            # período e cadência ilegível são esperas longas e quebram o
            # ciclo, que volta a ser tentado no próximo agendamento. Sem a
            # espera, um ciclo nunca passava de 1 post mesmo com
            # `max_posts_por_ciclo > 1` (intervalo de 300s > espaçamento de
            # 90s mandava `break` na segunda oferta sempre).
            #
            # A espera só compensa se couber NO ciclo: segurar o ciclo por mais
            # tempo que o intervalo entre ciclos atrasa o próximo agendamento
            # (o JobQueue não empilha execuções do mesmo job) e faz o bot
            # perder o ritmo. Nesse caso é melhor quebrar e deixar o próximo
            # ciclo, que chega antes, tentar de novo.
            cabe_no_ciclo = config.intervalo_minutos * 60
            if (motivo_ctrl.startswith("aguardando_intervalo_minimo")
                    and 0 < espera_s < cabe_no_ciclo):
                await asyncio.sleep(min(espera_s, config.intervalo_entre_posts_segundos))
                # A espera atravessa o fim da janela ativa: um post que espera
                # 18 min começando às 22:50 sairia às 23:08, e o painel mostra
                # "07:00-23:00". Checar de novo custa nada e faz a promessa
                # valer; o ciclo volta a ser tentado no próximo agendamento.
                if not dentro_do_horario():
                    log.info("[PUBLISH-CTRL] Intervalo terminou fora do "
                             "horário ativo (%s). Aguardando próximo ciclo.",
                             config.horario_ativo)
                    break
                pode_postar, motivo_ctrl, _ = publishing_controller.pode_publicar()
            if not pode_postar:
                log.info("[PUBLISH-CTRL] Publicação pausada (%s). Aguardando próximo ciclo.", motivo_ctrl)
                break

        try:
            await postar_oferta(bot, o, config.chat_id)
            publishing_controller.registrar_publicacao()
        except Exception as e:
            log.error("Falha ao postar '%s': %s", o.titulo[:60], e)
            continue
        db.registrar(o)
        a_liberar.discard(o.uid)      # registrada: a reserva sumiu com ela
        postadas += 1
        if o is not escolhidas[-1]:
            await asyncio.sleep(config.espacamento_segundos)

    # O que sobrou em a_liberar não foi publicado: seja porque faltou link de
    # afiliado, o Grok classificou como irrelevante, a pausa interrompeu o ciclo
    # (o `break` deixa as próximas intocadas) ou o envio falhou. Todas voltam
    # ao limbo para poderem ser tentadas de novo.
    for uid in a_liberar:
        db.liberar_reserva(uid)
    if a_liberar:
        log.info("[FILTER] %d oferta(s) voltaram ao limbo sem serem publicadas.", len(a_liberar))

    log.info("Ciclo: %d coletadas, %d aprovadas, %d postadas", len(brutas), len(boas), postadas)
    return postadas


def _e_id_produto(fonte_mod, oferta: Oferta) -> bool:
    """A plataforma sabe dizer se o id que ela montou e de um produto.

    `converter` monta o id de duas formas: achando o identificador na URL, ou
    caindo no ultimo segmento do caminho quando nao acha. A segunda devolve a
    slug da loja ou da pagina de cupom, e as duas chegam aqui com titulo
    generico e sem preco -- indistinguiveis a olho nu.

    Plataforma que nao expoe o predicado e tratada como "confia": so a Shopee,
    a Amazon e o Mercado Livre tem essa ambiguidade, e mudar o comportamento
    delas por conta de uma plataforma que nao pediu seria chute.
    """
    checa = getattr(fonte_mod, "e_id_produto", None)
    if checa is None:
        return True
    try:
        return bool(checa(oferta.id_produto))
    except Exception:
        return True


# Quantos links de uma mensagem testar antes de desistir. As mensagens reais do
# canal tem 2; 3 da folga sem transformar o scraper em varredura de rede.
MAX_LINKS_POR_MENSAGEM = 3


async def _converter_primeiro_produto(links_mp: list[dict]) -> tuple[Oferta | None, str]:
    """Converte os links da mensagem em ordem e devolve o primeiro produto de verdade.

    Nem toda mensagem de oferta tem o link do produto primeiro. No NERD OFERTAS
    o primeiro link e sempre o mesmo link de loja e o produto vem no segundo, e
    o pipeline ficava com a loja: todas as ofertas saiam com o mesmo uid, o
    dedup via-las como repetidas e 5 de cada 6 ofertas iam embora sem aviso.

    Se nenhum link for de produto, devolve a primeira conversao que deu certo
    -- o filtro de preco e o resto da qualidade decidem se ela serve. Descartar
    a mensagem inteira aqui seria trocar um erro visivel por um sumico.
    """
    reserva: Oferta | None = None
    url_reserva = ""
    for link in links_mp[:MAX_LINKS_POR_MENSAGEM]:
        url = link["url"]
        fonte_mod = link["fonte"]
        try:
            oferta = await asyncio.to_thread(fonte_mod.converter, url)
        except Exception as e:
            log.warning("[SCRAPER] Erro ao converter produto do link '%s': %s", url, e)
            continue
        if not oferta:
            continue
        if _e_id_produto(fonte_mod, oferta):
            log.info("[SCRAPER] Link de produto: '%s' -> %s", url, oferta.id_produto)
            return oferta, url
        if reserva is None:
            reserva, url_reserva = oferta, url
            log.info("[SCRAPER] '%s' nao e link de produto (id '%s'); tentando o proximo",
                     url, oferta.id_produto)
    if reserva is not None:
        log.info("[SCRAPER] Nenhum link de produto em %s; usando '%s' (id '%s')",
                 len(links_mp), url_reserva, reserva.id_produto)
    return reserva, url_reserva


def _aplicar_preco_texto(oferta: Oferta, pre: dict) -> None:
    """Preenche o preco da oferta com o que estava escrito na mensagem, se faltar.

    Quem decide a ordem e a confianca, nao a plataforma: um preco coletado da
    Shopee, da Amazon ou do Mercado Livre e dado de primeira linha e nunca e
    descartado. O texto da mensagem so entra no buraco que sobrou.

    O desconto fica por conta da property `Oferta.desconto`, que so calcula com
    preco e preco_original de verdade e com o original acima do atual. Por isso
    aqui nao se inventa `desconto_pct`: sem os dois numeros, nao ha desconto a
    calcular, e a property devolve None sozinha.
    """
    preco_txt = _preco_util(pre.get("preco_texto"))
    if preco_txt is None:
        return

    if _preco_util(oferta.preco) is not None:
        # A plataforma trouxe preco confiavel. Fica ele.
        return

    oferta.preco = preco_txt

    antigo_txt = _preco_util(pre.get("preco_antigo_texto"))
    if antigo_txt is not None and antigo_txt > preco_txt:
        oferta.preco_original = antigo_txt

    log.info("[SCRAPER] Preco obtido do texto da mensagem: R$ %.2f (%s)",
             preco_txt, oferta.plataforma)


async def processar_mensagem_telegram(
    texto: str,
    imagem_url: str | bytes | None = None,
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
        oferta, _url_usada = await _converter_primeiro_produto(links_mp)

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

    # 4.1 Preco escrito no texto da mensagem, como fallback.
    #
    # Fica aqui, num ponto unico, em vez de dentro de cada marketplace: e a
    # regra valida para todas elas, e a ordem de confianca e a mesma. Um preco
    # que veio da plataforma (API, pagina do produto) manda no texto -- sempre.
    # O texto so entra quando a plataforma nao trouxe preco utilizavel, que e o
    # caso dos short links da Shopee: o produto existe mas esta fora do catalogo
    # de ofertas da Open API, a API responde lista vazia, e antes disso a
    # oferta saia com preco None e era publicada sem nenhum preco.
    _aplicar_preco_texto(oferta, pre)

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

    # 7. Sistema central de filtros de qualidade de produto
    ok_filtro, motivo_filtro = passes_product_filters(oferta)
    if not ok_filtro:
        log.info("[FILTROS] Oferta '%s' rejeitada pelos filtros: %s", oferta.titulo[:50], motivo_filtro)
        if source_id and message_id:
            db.registrar_msg_telegram(source_id, message_id, oferta.uid, status=f"filtrada: {motivo_filtro}")
        return {"ok": False, "motivo": f"filtrada: {motivo_filtro}"}

    # 7.1 Deduplicação por produto, e não por mensagem.
    # A deduplicação acima (mensagens_telegram) é por (canal, message_id): o
    # mesmo produto anunciado em duas mensagens diferentes, ou anunciado num
    # canal e ainda encontrado na listagem de ofertas, passava duas vezes e era
    # postado duas vezes. Aqui conferimos contra `postadas` e reservamos o
    # produto, igual ao ciclo automático.
    # Mesma regra do ciclo: permanente, e só republica se o preço cair.
    preco_antigo = db.preco_ultima_postagem(oferta.uid)
    if preco_antigo is not None:
        caiu = oferta.preco is not None and oferta.preco < preco_antigo
        if not caiu:
            log.info("[FILTROS] Oferta '%s' ignorada: produto já postado (R$%.2f) e preço não caiu — só republica se o preço cair.",
                     oferta.titulo[:50], preco_antigo)
            if source_id and message_id:
                db.registrar_msg_telegram(source_id, message_id, oferta.uid, status="produto_ja_postado")
            return {"ok": False, "motivo": "produto_ja_postado"}

    if not db.reservar(oferta.uid):
        log.info("[FILTROS] Oferta '%s' ignorada: outro processo já está publicando este produto.",
                 oferta.titulo[:50])
        if source_id and message_id:
            db.registrar_msg_telegram(source_id, message_id, oferta.uid, status="produto_em_publicacao")
        return {"ok": False, "motivo": "produto_em_publicacao"}

    # 8. Controle de Velocidade e Pausas Globais
    if not dry_run:
        pode_postar, motivo_ctrl, espera_s = publishing_controller.pode_publicar()
        if not pode_postar:
            log.info("[PUBLISH-CTRL] Publicação retida pelo controle de velocidade: %s", motivo_ctrl)
            db.liberar_reserva(oferta.uid)
            if source_id and message_id:
                db.registrar_msg_telegram(source_id, message_id, oferta.uid, status=f"retida: {motivo_ctrl}")
            return {"ok": False, "motivo": f"controle_velocidade: {motivo_ctrl}", "espera_segundos": espera_s}

    # 9. Publicação (respeitando dry_run e canal de destino)
    if dry_run or not config.chat_id or not bot:
        log.info("[PUBLISH] [DRY-RUN] Oferta aprovada para publicação (chat=%s): %s", config.chat_id, oferta.titulo[:50])
        # Nada vai ser publicado, então a reserva não pode ficar segurada: um
        # dry-run bloquearia este produto por até uma hora.
        db.liberar_reserva(oferta.uid)
        if source_id and message_id:
            db.registrar_msg_telegram(source_id, message_id, oferta.uid, status="dry_run")
        return {"ok": True, "dry_run": True, "oferta": oferta}

    try:
        log.info("[PUBLISH] Publicando oferta no canal %s: %s", config.chat_id, oferta.titulo[:50])
        foto_da_mensagem = isinstance(oferta.imagem, (bytes, bytearray))
        await postar_oferta(bot, oferta, config.chat_id)
        publishing_controller.registrar_publicacao()
        if foto_da_mensagem:
            # A foto veio da mensagem do grupo, em bytes — ela já foi enviada,
            # mas não é um endereço de produto para a coluna `imagem` (que
            # guarda URLs da plataforma). Gravar bytes ali poluiria o banco e
            # quebraria quem relê a coluna; a coluna fica vazia de propósito.
            # Coluna nova não, valor falso não.
            oferta.imagem = None
        db.registrar(oferta)          # a reserva é consumida aqui
        if source_id and message_id:
            db.registrar_msg_telegram(source_id, message_id, oferta.uid, status="publicada")
        return {"ok": True, "oferta": oferta}
    except Exception as e:
        log.error("[PUBLISH] Falha ao publicar oferta: %s", e)
        db.liberar_reserva(oferta.uid)
        if source_id and message_id:
            db.registrar_msg_telegram(source_id, message_id, oferta.uid, status=f"erro: {e}")
        return {"ok": False, "motivo": f"erro_envio: {e}"}
