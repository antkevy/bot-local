"""Módulo de scraping e pré-processamento de mensagens de canais e grupos do Telegram.

Integrado ao pipeline central do Ofertas Pro e à camada de IA (Grok).
"""
from __future__ import annotations

import logging
import re
from typing import Any

from ..utils import extrair_urls

log = logging.getLogger("ofertas.scraper")


def e_postagem_propria(
    chat_id: str | int,
    bot_id: int | None = None,
    message_from_id: int | None = None,
    destination_chat_id: str | int | None = None,
) -> bool:
    """Evita loops infinitos: verifica se a mensagem originou do próprio bot ou do canal de destino."""
    chat_str = str(chat_id).strip()
    dest_str = str(destination_chat_id or "").strip()

    # Se o chat de origem for o mesmo canal de destino do bot
    if dest_str and (chat_str == dest_str or chat_str == dest_str.lstrip("-100")):
        return True

    # Se o autor da mensagem for o próprio bot
    if bot_id and message_from_id and bot_id == message_from_id:
        return True

    return False


def pre_processar_mensagem(texto: str) -> dict[str, Any]:
    """Pré-processamento da mensagem bruta: extrai URLs, detecta marketplaces e pistas de cupom."""
    from . import detectar_fonte

    texto_limpo = texto.strip() if texto else ""
    urls = extrair_urls(texto_limpo)

    links_por_marketplace: list[dict[str, Any]] = []
    for u in urls:
        fonte = detectar_fonte(u)
        if fonte:
            nome_plat = getattr(fonte, "NOME_PLATAFORMA", getattr(fonte, "__name__", "desconhecido")).split(".")[-1]
            links_por_marketplace.append({
                "url": u,
                "fonte": fonte,
                "plataforma": nome_plat,
            })

    # Pistas simples de cupom (sem substituir a IA, apenas como apoio)
    cupons_candidatos = re.findall(r"(?:cupom|código|code)[:\s]+([A-Z0-9_-]{4,25})\b", texto_limpo, re.IGNORECASE)

    return {
        "texto_original": texto_limpo,
        "urls": urls,
        "links_marketplace": links_por_marketplace,
        "cupons_candidatos": cupons_candidatos,
        "tem_links_afiliados_potenciais": bool(links_por_marketplace),
    }
