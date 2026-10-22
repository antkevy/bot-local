"""Padrão central de identificação e apresentação de marketplaces.

Garante que nomes, emojis e rótulos de todas as plataformas parceiras sejam
consistentes em todo o sistema (logs, templates, mensagens de Telegram e painel).
"""
from __future__ import annotations

from urllib.parse import urlsplit

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


def host_de(url: str) -> str:
    """Host de uma URL, aceitando também a forma sem protocolo.

    Espelha `amazon._host_de`, que resolve o mesmo problema para os links
    curtos colados sem "https://" (`link.amazon/...`). Sem o "//" descartável,
    o urlsplit leria o domínio como caminho e nenhuma comparação casaria.
    """
    bruto = str(url or "").strip()
    if "//" not in bruto:
        bruto = "//" + bruto
    try:
        return (urlsplit(bruto).hostname or "").lower()
    except ValueError:
        return ""


def url_pertence(url: str, dominios) -> bool:
    """True se o HOST da URL for um dos domínios (ou subdomínio deles).

    A comparação é por host, nunca por substring: com `"amazon.com" in url`,
    `https://notamazon.com/x` e `https://amazon.com.br.evil.tld/x` passavam
    como Amazon — e o pipeline pagava a tag do usuário e publicava o link de
    um site que não é a loja. É a mesma correção já aplicada em `amazon.py`.
    """
    host = host_de(url)
    if not host:
        return False
    return any(host == d or host.endswith("." + d) for d in dominios)


def normalizar_marketplace(nome: str) -> str:
    """Normaliza strings variadas para a chave padrão do marketplace."""
    if not nome:
        return ""
    limpo = str(nome).lower().strip().replace(" ", "").replace("_", "").replace("-", "")
    # Comparação por prefixo conhecido, não por substring solta. Com
    # `"ali" in limpo`, qualquer rótulo como "qualidade" virava AliExpress —
    # e o rótulo errado ia para a legenda do post.
    if limpo in ("ml", "mercado") or limpo.startswith(("mercadolivre", "mercadolibre", "meli")):
        return "mercadolivre"
    if limpo.startswith("amazon") or limpo == "amz":
        return "amazon"
    if limpo.startswith("shopee") or limpo.startswith("shp"):
        return "shopee"
    if limpo.startswith("aliexpress") or limpo == "ali":
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

