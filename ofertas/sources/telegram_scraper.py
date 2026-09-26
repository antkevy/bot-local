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


def normalizar_username_telegram(fonte: str) -> str:
    """Normaliza strings como @grupo, https://t.me/grupo, t.me/grupo ou -1001234."""
    if not fonte:
        return ""
    limpo = str(fonte).strip()
    if limpo.startswith("https://t.me/"):
        limpo = limpo.replace("https://t.me/", "")
    elif limpo.startswith("http://t.me/"):
        limpo = limpo.replace("http://t.me/", "")
    elif limpo.startswith("t.me/"):
        limpo = limpo.replace("t.me/", "")
    limpo = limpo.rstrip("/")
    if limpo.startswith("-") or limpo.isdigit():
        return limpo
    if not limpo.startswith("@"):
        limpo = f"@{limpo}"
    return limpo


async def testar_conexao_fonte(fonte_str: str, bot: Any = None) -> dict:
    """Testa a conectividade real com um canal/grupo usando Telegram Bot API ou telethon."""
    username = normalizar_username_telegram(fonte_str)
    if not username:
        return {"ok": False, "erro": "Username ou ID vazio."}

    # 1. Se bot do python-telegram-bot estiver disponível
    if bot:
        try:
            chat = await bot.get_chat(username)
            return {
                "ok": True,
                "chat_id": str(chat.id),
                "nome": chat.title or chat.username or username,
                "tipo": getattr(chat, "type", "canal"),
                "username": f"@{chat.username}" if chat.username else username,
            }
        except Exception as e:
            return {"ok": False, "erro": f"Telegram: {e}"}

    # 2. Tentativa direta via HTTP com token do bot se disponível
    from ..config import config
    if config.bot_token:
        import requests
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{config.bot_token}/getChat",
                params={"chat_id": username},
                timeout=10,
            )
            dados = r.json()
            if dados.get("ok"):
                c = dados["result"]
                return {
                    "ok": True,
                    "chat_id": str(c.get("id")),
                    "nome": c.get("title") or c.get("username") or username,
                    "tipo": c.get("type", "canal"),
                    "username": f"@{c.get('username')}" if c.get("username") else username,
                }
            else:
                return {"ok": False, "erro": dados.get("description", "Canal/grupo não encontrado")}
        except Exception as e:
            return {"ok": False, "erro": f"Erro de conexão com Telegram: {e}"}

    return {"ok": True, "chat_id": username, "nome": username, "tipo": "canal", "username": username}

