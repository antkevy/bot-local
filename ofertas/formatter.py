from __future__ import annotations

from html import escape

from .marketplaces import get_marketplace_display
from .models import Oferta


def preco_br(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def montar_caption(o: Oferta) -> str:
    """Monta a legenda/template formatada para publicação no Telegram."""
    linhas = [f"🔥 <b>{escape(o.titulo[:180])}</b>", ""]

    preco_ant = o.preco_original or o.preco_antigo

    # Preço e Desconto real
    if o.preco and preco_ant and preco_ant > o.preco:
        linhas.append(f"❌ De: <s>{preco_br(preco_ant)}</s>")
        desc_val = o.desconto
        if not desc_val and preco_ant > o.preco:
            desc_val = round(((preco_ant - o.preco) / preco_ant) * 100)
        selo = f"  🔻 <b>{desc_val}% OFF</b>" if desc_val else ""
        linhas.append(f"✅ Por: <b>{preco_br(o.preco)}</b>{selo}")
    elif o.preco:
        # Produto sem preço anterior / sem desconto: NÃO inventar De/Por
        linhas.append(f"💰 <b>{preco_br(o.preco)}</b>")

    # Cupom de desconto
    if o.cupom:
        cupom_txt = f"🏷️ Cupom: <code>{escape(o.cupom)}</code>"
        if o.beneficio_cupom:
            cupom_txt += f" ({escape(o.beneficio_cupom)})"
        linhas.append(cupom_txt)

    # Avaliação e Vendas estruturadas
    badges = []
    if o.avaliacao:
        badges.append(f"⭐ {o.avaliacao:.1f}")
    if o.vendas:
        vendas_fmt = f"{o.vendas:,}".replace(",", ".")
        badges.append(f"🛒 {vendas_fmt} vendidos")
    if badges:
        linhas.append(" · ".join(badges))

    # Informações extras (Garante que comissão NUNCA vaze para a postagem)
    if o.extra:
        extra_limpo = o.extra
        if "comissão" not in extra_limpo.lower() and "commission" not in extra_limpo.lower():
            linhas.append(escape(extra_limpo))

    mp = get_marketplace_display(o.plataforma)
    linhas += ["", mp["label"]]
    return "\n".join(linhas)


formatar_mensagem = montar_caption

