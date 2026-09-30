"""Fonte Nerd Ofertas: alertas de ofertas e cupons do alerta.nerdofertas.com.

O site é um SPA React, mas expõe um feed JSON público em
`/api/app/{slug}/offers`: cada item traz o texto do alerta (título, preço,
cupom e link), a foto em `/media/...`, o link da mensagem original no Telegram e
o canal de origem. Um GET resolve — não é preciso raspar HTML nem abrir
navegador.

Cada alerta entra pelo MESMO caminho das mensagens do Telegram
(`pipeline.processar_mensagem_telegram`): o link é convertido pelo conversor da
plataforma, que devolve o link de afiliado do dono, e cupom/preço saem do texto
(IA). Alerta do canal que é o próprio destino é ignorado, e o que não virar
link de afiliado é descartado — nunca sai link de terceiro.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from .. import db
from ..config import config
from ..utils import sessao

log = logging.getLogger("ofertas.nerdofertas")

BASE_PADRAO = "https://alerta.nerdofertas.com"
SLUG_PADRAO = "nerdavisosbot"

_RE_TME = re.compile(r"(?:https?://)?t\.me/([A-Za-z0-9_+-]+)(?:/|$)")


def _cfg() -> dict:
    return getattr(config, "fonte_nerdofertas", None) or {}


def slug() -> str:
    return str(_cfg().get("slug") or SLUG_PADRAO).strip()


def base() -> str:
    return str(_cfg().get("base") or BASE_PADRAO).rstrip("/")


def e_ativa() -> bool:
    return bool(_cfg().get("ativa"))


def _dry_run_padrao() -> bool:
    return bool(_cfg().get("dry_run", False))


def _canais_ignorados() -> set[str]:
    brutos = _cfg().get("ignorar_canais") or []
    if isinstance(brutos, str):
        brutos = [brutos]
    return {
        str(c).strip().lower().removeprefix("https://t.me/").removeprefix("t.me/").lstrip("@")
        for c in brutos if str(c).strip()
    }


def canal_do_alerta(item: dict) -> str:
    """Username do canal que publicou o alerta, extraído do link t.me."""
    m = _RE_TME.search(str(item.get("link") or ""))
    return m.group(1).lower() if m else ""


def e_canal_proprio(item: dict, ignorados: set[str]) -> bool:
    canal = canal_do_alerta(item)
    return bool(canal) and canal in ignorados


def buscar_alertas() -> list[dict]:
    """GET do feed público e devolve a lista de alertas."""
    url = f"{base()}/api/app/{slug()}/offers"
    r = sessao().get(url, timeout=20)
    r.raise_for_status()
    itens = (r.json() or {}).get("items") or []
    log.info("[NERDOFERTAS] Feed devolveu %d alerta(s) (slug=%s).", len(itens), slug())
    return [i for i in itens if isinstance(i, dict)]


def url_da_foto(item: dict) -> str:
    """URL absoluta da foto do alerta (o feed devolve um caminho relativo)."""
    foto = str(item.get("photo") or "").strip()
    if not foto:
        return ""
    if foto.startswith("http"):
        return foto
    return f"{base()}/{foto.lstrip('/')}"


def baixar_foto(url: str) -> bytes | None:
    """Baixa a foto do alerta em bytes.

    A API responde `application/octet-stream` e o caminho não tem extensão:
    mandar a URL ao Telegram faria a foto ser recusada e a postagem cairia para
    texto. Em bytes, o Telegram identifica a imagem pelo conteúdo.
    """
    if not url:
        return None
    try:
        r = sessao().get(url, timeout=20)
        r.raise_for_status()
        return r.content or None
    except Exception as e:
        log.warning("[NERDOFERTAS] Não consegui baixar a foto '%s': %s", url[:80], e)
        return None


async def processar_alertas(bot: Any = None, dry_run: bool | None = None) -> dict[str, Any]:
    """Busca o feed e joga cada alerta novo no pipeline de mensagens.

    Devolve um resumo (vistos/processados/postados/motivos) em vez de levantar:
    uma falha do feed é do tipo que se registra e tenta de novo no próximo
    ciclo, não o tipo que derruba o ciclo inteiro.
    """
    from .. import pipeline  # import tardio: o pipeline importa as fontes

    if dry_run is None:
        dry_run = _dry_run_padrao()

    resumo: dict[str, Any] = {
        "ok": True, "ativo": e_ativa(), "vistos": 0, "processados": 0, "postados": 0,
        "ignorados_proprio": 0, "duplicados": 0, "motivos": {},
    }
    if not e_ativa():
        return resumo

    try:
        itens = buscar_alertas()
    except Exception as e:
        log.warning("[NERDOFERTAS] Falha ao buscar o feed: %s", e)
        return {**resumo, "ok": False, "erro": str(e)}

    ignorados = _canais_ignorados()
    fonte_id = f"nerdofertas:{slug()}"
    resumo["vistos"] = len(itens)

    for item in itens:
        item_id = int(item.get("id") or 0)
        texto = str(item.get("text") or "").strip()
        if not item_id or not texto:
            continue
        if e_canal_proprio(item, ignorados):
            resumo["ignorados_proprio"] += 1
            log.info("[NERDOFERTAS] Alerta %d ignorado: é do canal de destino.", item_id)
            continue
        # O feed traz os mesmos itens mais recentes a cada consulta; o pipeline
        # também checa, mas aqui o corte vem antes do download da foto.
        if db.ja_processada_msg_telegram(fonte_id, item_id):
            resumo["duplicados"] += 1
            continue

        foto = None
        url_foto = url_da_foto(item)
        if url_foto:
            foto = await asyncio.to_thread(baixar_foto, url_foto)

        try:
            r = await pipeline.processar_mensagem_telegram(
                texto=texto,
                imagem_url=foto,
                source_id=fonte_id,
                message_id=item_id,
                bot=bot,
                dry_run=bool(dry_run),
            )
        except Exception as e:
            log.warning("[NERDOFERTAS] Alerta %d falhou no pipeline: %s", item_id, e)
            resumo["motivos"]["erro"] = resumo["motivos"].get("erro", 0) + 1
            continue

        resumo["processados"] += 1
        if r.get("ok") and not r.get("dry_run"):
            resumo["postados"] += 1
        motivo = r.get("motivo") or ("dry_run" if r.get("dry_run") else "ok")
        resumo["motivos"][motivo] = resumo["motivos"].get(motivo, 0) + 1

    log.info("[NERDOFERTAS] %d alerta(s) no feed, %d processado(s), %d postado(s).",
             resumo["vistos"], resumo["processados"], resumo["postados"])
    return resumo