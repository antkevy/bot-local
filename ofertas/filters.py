"""Sistema central de filtros avançados de qualidade de produtos e ofertas.

Valida ofertas capturadas de scraping de grupos/canais e fontes automáticas
segundo regras de estrelas, vendas, descontos, preços e palavras bloqueadas.
"""
from __future__ import annotations

import logging
from typing import Tuple

from .config import config
from .formatter import _preco_util
from .models import Oferta

log = logging.getLogger("ofertas.filters")


def passes_product_filters(oferta: Oferta) -> Tuple[bool, str]:
    """Verifica se a oferta atende aos critérios configurados de qualidade.
    
    Retorna (True, "aprovado") ou (False, motivo_da_rejeicao).
    """
    if not oferta.titulo:
        return False, "sem_titulo"

    # 0. Preco utilizavel.
    #
    # Sem isto, uma oferta sem preco vira post vazio: o `montar_caption` tem
    # poucos campos para preencher e, sem preco e sem desconto, sobra apenas o
    # titulo generico e a assinatura do marketplace. Foi exatamente o que
    # aconteceu com os links curtos da Shopee: o produto esta no canal, mas
    # fora do catalogo de ofertas da Open API, entao `converter` cai no
    # fallback e devolve titulo "Oferta Shopee" com preco None -- que passava
    # por todos os filtros e era publicado.
    #
    # A definicao de "preco utilizavel" e a mesma do formatter, de proposito:
    # duas copias divergem, e a que diverge e a que deixa passar lixo.
    if _preco_util(oferta.preco) is None:
        log.info("[FILTER] Produto '%s' ignorado: sem_preco", (oferta.titulo or "")[:40])
        return False, "sem_preco"

    # 1. Filtro de palavras bloqueadas
    titulo_lower = oferta.titulo.lower()
    for pb in config.palavras_bloqueadas:
        if pb and pb in titulo_lower:
            motivo = f"palavra_bloqueada: '{pb}'"
            log.info("[FILTER] Produto '%s' ignorado: %s", oferta.titulo[:40], motivo)
            return False, motivo

    # 2. Filtro de Avaliação / Estrelas (Rating)
    if config.avaliacao_minima and config.avaliacao_minima > 0:
        if oferta.avaliacao is None:
            if not config.permitir_sem_avaliacao:
                motivo = f"avaliacao_ausente (politica: rejeitar sem estrelas, minimo={config.avaliacao_minima})"
                log.info("[FILTER] Produto '%s' ignorado: %s", oferta.titulo[:40], motivo)
                return False, motivo
        else:
            if oferta.avaliacao < config.avaliacao_minima:
                motivo = f"avaliacao_baixa (nota {oferta.avaliacao:.1f} < minimo {config.avaliacao_minima:.1f})"
                log.info("[FILTER] Produto '%s' ignorado: %s", oferta.titulo[:40], motivo)
                return False, motivo

    # 3. Filtro de Vendas Mínimas
    if config.vendas_minimas and config.vendas_minimas > 0:
        if oferta.vendas is None:
            if not config.permitir_sem_vendas:
                motivo = f"vendas_ausente (politica: rejeitar sem vendas, minimo={config.vendas_minimas})"
                log.info("[FILTER] Produto '%s' ignorado: %s", oferta.titulo[:40], motivo)
                return False, motivo
        else:
            if oferta.vendas < config.vendas_minimas:
                motivo = f"vendas_insuficientes ({oferta.vendas} < minimo {config.vendas_minimas})"
                log.info("[FILTER] Produto '%s' ignorado: %s", oferta.titulo[:40], motivo)
                return False, motivo

    # 4. Filtro de Preço Mínimo / Máximo
    if oferta.preco is not None:
        if config.preco_minimo and config.preco_minimo > 0 and oferta.preco < config.preco_minimo:
            motivo = f"preco_abaixo_minimo (R${oferta.preco:.2f} < R${config.preco_minimo:.2f})"
            log.info("[FILTER] Produto '%s' ignorado: %s", oferta.titulo[:40], motivo)
            return False, motivo
        if config.preco_maximo and config.preco_maximo > 0 and oferta.preco > config.preco_maximo:
            motivo = f"preco_acima_maximo (R${oferta.preco:.2f} > R${config.preco_maximo:.2f})"
            log.info("[FILTER] Produto '%s' ignorado: %s", oferta.titulo[:40], motivo)
            return False, motivo

    # 5. Filtro de Desconto
    desconto_min = getattr(config, "desconto_minimo_pct", 0) or getattr(config, "desconto_minimo", 0) or 0
    if desconto_min and desconto_min > 0:
        desc = oferta.desconto
        if desc is None:
            if not getattr(config, "permitir_sem_desconto", True):
                motivo = f"sem_desconto (politica: rejeitar sem desconto, minimo={desconto_min}%)"
                log.info("[FILTER] Produto '%s' ignorado: %s", oferta.titulo[:40], motivo)
                return False, motivo
        else:
            if desc < desconto_min:
                motivo = f"desconto_insuficiente ({desc}% < minimo {desconto_min}%)"
                log.info("[FILTER] Produto '%s' ignorado: %s", oferta.titulo[:40], motivo)
                return False, motivo

    return True, "aprovado"
