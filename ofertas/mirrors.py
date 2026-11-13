"""Espelhamento: replicar cada oferta para canais/grupos extras.

O ScanHub chamava isso de "mirrors": uma lista de destinos, cada um com seu
próprio interruptor. Aqui a ideia é a mesma, mas sem tocar no pipeline — quem
quiser espelhar lê `destinos_ativos()` e publica a mesma oferta lá. Enquanto
`extras.espelhamento` estiver desligado no config.yaml, nada lê esta tabela.

Regra de entrada: o `chat_id` é a chave. Aceita `@canal`, `-100...` ou o id
numérico do Telegram. Duplicar o mesmo destino é atualizado, não duplicado.
"""
from __future__ import annotations

import datetime as dt
import logging
import re

from .extra_db import conn

log = logging.getLogger("ofertas.mirrors")

_CHAT_VALIDO = re.compile(r"^(@[A-Za-z][A-Za-z0-9_]{3,31}|-?\d{5,20})$")


class ErroEspelhamento(ValueError):
    """Entrada recusada com uma mensagem que pode ir direto para a tela."""


def _normalizar_chat(chat_id: str) -> str:
    bruto = str(chat_id or "").strip()
    if not _CHAT_VALIDO.match(bruto):
        raise ErroEspelhamento(
            "Destino inválido: use @canal ou o id numérico do Telegram."
        )
    return bruto


def adicionar(chat_id: str, nome: str = "") -> dict:
    """Cadastra (ou atualiza) um destino de espelhamento."""
    destino = _normalizar_chat(chat_id)
    agora = dt.datetime.now().isoformat(timespec="seconds")
    with conn() as c:
        c.execute(
            "INSERT INTO mirrors (chat_id, nome, ativo, criado_em)"
            " VALUES (?, ?, 1, ?)"
            " ON CONFLICT(chat_id) DO UPDATE SET nome = excluded.nome",
            (destino, str(nome or "").strip(), agora),
        )
        linha = c.execute(
            "SELECT id, chat_id, nome, ativo, criado_em FROM mirrors"
            " WHERE chat_id = ?", (destino,),
        ).fetchone()
    log.info("Espelho cadastrado: %s", destino)
    return _dict(linha)


def listar() -> list[dict]:
    with conn() as c:
        linhas = c.execute(
            "SELECT id, chat_id, nome, ativo, criado_em FROM mirrors"
            " ORDER BY criado_em ASC, id ASC"
        ).fetchall()
    return [_dict(ln) for ln in linhas]


def alternar(mirror_id: int, ativo: bool) -> dict | None:
    """Liga/desliga um destino. Devolve a linha nova, ou None se sumiu."""
    with conn() as c:
        c.execute("UPDATE mirrors SET ativo = ? WHERE id = ?",
                  (1 if ativo else 0, int(mirror_id)))
        linha = c.execute(
            "SELECT id, chat_id, nome, ativo, criado_em FROM mirrors WHERE id = ?",
            (int(mirror_id),),
        ).fetchone()
    return _dict(linha) if linha else None


def remover(mirror_id: int) -> bool:
    with conn() as c:
        cur = c.execute("DELETE FROM mirrors WHERE id = ?", (int(mirror_id),))
    return cur.rowcount > 0


def destinos_ativos() -> list[str]:
    """Chat ids ligados agora — a lista que quem espelha deve consumir."""
    with conn() as c:
        linhas = c.execute(
            "SELECT chat_id FROM mirrors WHERE ativo = 1 ORDER BY id ASC"
        ).fetchall()
    return [ln[0] for ln in linhas]


def _dict(linha) -> dict:
    if not linha:
        return {}
    return {"id": linha[0], "chat_id": linha[1], "nome": linha[2],
            "ativo": bool(linha[3]), "criado_em": linha[4]}
