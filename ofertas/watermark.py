"""Marca d'água: assinatura aplicada ao texto antes de publicar.

O ScanHub tratava isso como um preset (onde a assinatura entra) mais um @. O
mesmo modelo aqui, com a garantia que importa: aplicar duas vezes não duplica
a assinatura, e desligar não altera nenhum texto.

Presets:
    final  -> o texto, depois uma linha com "👉 @canal"
    topo   -> "👉 @canal" e uma linha em branco, depois o texto
    sufixo -> o texto e o @ na mesma linha, separado por espaço

Nada aqui é chamado pelo pipeline atual: quem publicar pelo espelhamento (ou
por um disparo) pode passar o texto por `aplicar()`.
"""
from __future__ import annotations

import datetime as dt
import re

from .extra_db import conn

PRESETS = ("final", "topo", "sufixo")
_HANDLE_VALIDO = re.compile(r"^@[A-Za-z][A-Za-z0-9_]{3,31}$")


class ErroMarcaDagua(ValueError):
    """Entrada recusada com mensagem pronta para a tela."""


def _normalizar_handle(handle: str) -> str:
    texto = str(handle or "").strip()
    if not texto:
        return ""
    if not texto.startswith("@"):
        texto = "@" + texto
    if not _HANDLE_VALIDO.match(texto):
        raise ErroMarcaDagua(
            "O @ precisa ter de 4 a 32 caracteres e começar com uma letra."
        )
    return texto


def obter() -> dict:
    with conn() as c:
        linha = c.execute(
            "SELECT preset, handle, ativo FROM marca_dagua WHERE id = 1"
        ).fetchone()
    if not linha:
        return {"preset": "final", "handle": "", "ativo": False}
    return {"preset": linha[0], "handle": linha[1], "ativo": bool(linha[2])}


def configurar(preset: str = "final", handle: str = "", ativo: bool = True) -> dict:
    preset = str(preset or "final").strip().lower()
    if preset not in PRESETS:
        raise ErroMarcaDagua("Preset inválido: use final, topo ou sufixo.")
    handle = _normalizar_handle(handle)
    if ativo and not handle:
        raise ErroMarcaDagua("Informe o @ da marca d'água para ativá-la.")
    agora = dt.datetime.now().isoformat(timespec="seconds")
    with conn() as c:
        c.execute(
            "INSERT INTO marca_dagua (id, preset, handle, ativo)"
            " VALUES (1, ?, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET"
            " preset = excluded.preset,"
            " handle = excluded.handle,"
            " ativo = excluded.ativo",
            (preset, handle, 1 if ativo else 0),
        )
    return obter()


def aplicar(texto: str) -> str:
    """Aplica a marca d'água configurada. Desligada ou sem handle = texto puro."""
    cfg = obter()
    if not cfg["ativo"] or not cfg["handle"]:
        return texto
    corpo = str(texto or "").rstrip()
    assinatura = cfg["handle"]
    if assinatura in corpo:
        return corpo          # já assinado: não duplica
    if cfg["preset"] == "topo":
        return f"{assinatura}\n\n{corpo}" if corpo else assinatura
    if cfg["preset"] == "sufixo":
        return f"{corpo} {assinatura}" if corpo else assinatura
    return f"{corpo}\n\n👉 {assinatura}" if corpo else assinatura
