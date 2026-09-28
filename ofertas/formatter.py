from __future__ import annotations

import math
from html import escape

from .marketplaces import get_marketplace_display
from .models import Oferta


def preco_br(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def _preco_util(valor) -> float | None:
    """Devolve o preço só se for um número positivo e finito.

    Parse de preço de marketplace é a origem mais comum de valor sem sentido:
    uma página bloqueada devolve string vazia, um "de R$" solto vira 0, e um
    campo com sinal trocado vira negativo. Nada disso pode chegar à postagem
    como "R$ -10,00" ou como um desconto de -300%.
    """
    if valor is None or isinstance(valor, bool):
        return None
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v) or v <= 0:
        return None
    return v


def _desconto_util(valor) -> int | None:
    """Desconto só se estiver no intervalo 1..99. Fora disso é ruído da página."""
    if valor is None or isinstance(valor, bool):
        return None
    try:
        d = int(round(float(valor)))
    except (TypeError, ValueError):
        return None
    return d if 1 <= d <= 99 else None


def montar_caption(o: Oferta) -> str:
    """Monta a legenda/template formatada para publicação no Telegram."""
    linhas = [f"🔥 <b>{escape(o.titulo[:180])}</b>", ""]

    preco = _preco_util(o.preco)
    preco_ant = _preco_util(o.preco_original) or _preco_util(o.preco_antigo)

    # Preço e Desconto real
    if preco and preco_ant and preco_ant > preco:
        linhas.append(f"❌ De: <s>{preco_br(preco_ant)}</s>")
        desc_val = _desconto_util(o.desconto)
        if not desc_val and preco_ant > preco:
            desc_val = round(((preco_ant - preco) / preco_ant) * 100)
        selo = f"  🔻 <b>{desc_val}% OFF</b>" if desc_val else ""
        linhas.append(f"✅ Por: <b>{preco_br(preco)}</b>{selo}")
    elif preco:
        # Produto sem preço anterior / sem desconto: NÃO inventar De/Por
        linhas.append(f"💰 <b>{preco_br(preco)}</b>")

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

