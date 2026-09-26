"""Padrão central de identificação e apresentação de marketplaces.

Garante que nomes, emojis e rótulos de todas as plataformas parceiras sejam
consistentes em todo o sistema (logs, templates, mensagens de Telegram e painel).
"""
from __future__ import annotations

_MARKETPLACE_MAP = {
    "mercadolivre": {
        "key": "mercadolivre",
        "name": "Mercado Livre",
        "emoji": "💛",
        "label": "💛 Mercado Livre",
    },
    "amazon": {
        "key": "amazon",
        "name": "Amazon",
        "emoji": "📦",
        "label": "📦 Amazon",
    },
    "shopee": {
        "key": "shopee",
        "name": "Shopee",
        "emoji": "🧡",
        "label": "🧡 Shopee",
    },
    "aliexpress": {
        "key": "aliexpress",
        "name": "AliExpress",
        "emoji": "🔴",
        "label": "🔴 AliExpress",
    },
}


def normalizar_marketplace(nome: str) -> str:
    """Normaliza strings variadas para a chave padrão do marketplace."""
    if not nome:
        return ""
    limpo = str(nome).lower().strip().replace(" ", "").replace("_", "").replace("-", "")
    if "mercado" in limpo or "meli" in limpo or "ml" == limpo:
        return "mercadolivre"
    if "amazon" in limpo or "amz" in limpo:
        return "amazon"
    if "shopee" in limpo or "shp" in limpo:
        return "shopee"
    if "aliexpress" in limpo or "ali" in limpo:
        return "aliexpress"
    return limpo


def get_marketplace_display(plataforma: str) -> dict:
    """Retorna dicionário padronizado com name, emoji e label para exibição."""
    chave = normalizar_marketplace(plataforma)
    if chave in _MARKETPLACE_MAP:
        d = dict(_MARKETPLACE_MAP[chave])
        d["nome"] = d["name"]
        return d
    
    nome_bonito = plataforma.capitalize() if plataforma else "Marketplace"
    return {
        "key": chave or "outro",
        "name": nome_bonito,
        "nome": nome_bonito,
        "emoji": "🛍️",
        "label": f"🛍️ {nome_bonito}",
    }


def formatar_marketplace_postagem(plataforma: str) -> str:
    """Retorna string formatada para postagem: '🔴 AliExpress', '💛 Mercado Livre', etc."""
    disp = get_marketplace_display(plataforma)
    return f"{disp['emoji']} {disp['name']}"

