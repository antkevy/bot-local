"""Proteção: varrer fontes suspeitas e SÓ remover depois da revisão.

O ScanHub chamava isso de "protection" e removia ~1 pessoa a cada 3s, mas o
fluxo importante era outro: primeiro um scan, depois a lista para revisar, e
só então `confirm` (ou `cancel`). É esse fluxo que reproduzimos — remoção
automática de fonte é o tipo de ação que não pode acontecer por engano.

O que conta como suspeita (e nada além disso):
  - fonte desativada no painel;
  - fonte que nunca processou uma mensagem;
  - fonte sem processar nada há mais de `dias` dias.

A varredura NUNCA mexe em `postadas`, `mensagens_telegram` ou em qualquer
fonte com atividade recente. Confirmar remove apenas as fontes listadas no
scan, pelo `chat_id`, usando a função que o painel já usa.
"""
from __future__ import annotations

import datetime as dt
import logging
import secrets

from . import db
from .extra_db import conn

log = logging.getLogger("ofertas.protection")

DIAS_PADRAO = 14


class ErroProtecao(ValueError):
    """Entrada recusada com mensagem pronta para a tela."""


def iniciar_scan(dias: int = DIAS_PADRAO,
                 agora: dt.datetime | None = None) -> dict:
    """Monta a lista de candidatos e a guarda para revisão. Não remove nada."""
    try:
        dias = int(dias)
    except (TypeError, ValueError):
        raise ErroProtecao("O intervalo em dias precisa ser um número.")
    if dias < 1 or dias > 365:
        raise ErroProtecao("O intervalo precisa ficar entre 1 e 365 dias.")

    agora = agora or dt.datetime.now()
    limite = agora - dt.timedelta(days=dias)
    scan_id = secrets.token_hex(8)
    criado = agora.isoformat(timespec="seconds")

    alvos: list[dict] = []
    for fonte in db.listar_fontes_telegram():
        chat_id = str(fonte.get("chat_id") or "")
        if not chat_id:
            continue
        motivo = _motivo(fonte, limite)
        if motivo:
            alvos.append({"chave": chat_id, "chat_id": chat_id,
                          "nome": str(fonte.get("nome") or ""), "motivo": motivo})

    with conn() as c:
        c.execute(
            "INSERT INTO protection_scans (id, status, criado_em) VALUES (?, 'revisao', ?)",
            (scan_id, criado),
        )
        for alvo in alvos:
            c.execute(
                "INSERT INTO protection_alvos"
                " (scan_id, chave, chat_id, nome, motivo, status)"
                " VALUES (?, ?, ?, ?, ?, 'pendente')",
                (scan_id, alvo["chave"], alvo["chat_id"], alvo["nome"], alvo["motivo"]),
            )
    log.info("Scan de proteção %s: %d fonte(s) para revisar", scan_id, len(alvos))
    return obter_scan(scan_id) or {}


def _motivo(fonte: dict, limite: dt.datetime) -> str:
    """Por que esta fonte entrou na revisão ('' = está saudável)."""
    if not fonte.get("ativa", 1):
        return "fonte desativada no painel"
    ultimo = fonte.get("ultimo_processamento")
    if not ultimo:
        return "nunca processou nenhuma mensagem"
    try:
        quando = dt.datetime.fromisoformat(str(ultimo))
    except (TypeError, ValueError):
        return "data da última mensagem inválida"
    if quando < limite:
        return f"sem mensagens desde {quando:%d/%m/%Y %H:%M}"
    return ""


def obter_scan(scan_id: str) -> dict | None:
    with conn() as c:
        linha = c.execute(
            "SELECT id, status, criado_em, confirmado_em"
            " FROM protection_scans WHERE id = ?", (str(scan_id or ""),),
        ).fetchone()
        if not linha:
            return None
        alvos = c.execute(
            "SELECT chave, chat_id, nome, motivo, status"
            " FROM protection_alvos WHERE scan_id = ? ORDER BY chat_id",
            (str(scan_id),),
        ).fetchall()
    return {
        "id": linha[0], "status": linha[1], "criado_em": linha[2],
        "confirmado_em": linha[3],
        "alvos": [{"chave": a[0], "chat_id": a[1], "nome": a[2],
                   "motivo": a[3], "status": a[4]} for a in alvos],
    }


def listar_scans(limite: int = 20) -> list[dict]:
    with conn() as c:
        linhas = c.execute(
            "SELECT id FROM protection_scans ORDER BY criado_em DESC LIMIT ?",
            (int(limite),),
        ).fetchall()
    return [obter_scan(ln[0]) for ln in linhas]


def confirmar(scan_id: str, chaves) -> dict:
    """Remove SÓ as chaves revisadas e aprovadas. Devolve o scan atualizado."""
    scan = obter_scan(scan_id)
    if not scan:
        raise ErroProtecao("Scan não encontrado.")
    if scan["status"] != "revisao":
        raise ErroProtecao("Este scan já foi concluído ou cancelado.")
    if isinstance(chaves, str):
        chaves = [chaves]
    aprovadas = {str(k) for k in (chaves or []) if str(k).strip()}
    if not aprovadas:
        raise ErroProtecao("Selecione ao menos uma fonte para remover.")
    validas = {a["chave"] for a in scan["alvos"] if a["status"] == "pendente"}
    desconhecidas = aprovadas - validas
    if desconhecidas:
        raise ErroProtecao("Há fontes fora deste scan na seleção.")

    removidas = 0
    with conn() as c:
        for chave in aprovadas:
            try:
                db.remover_fonte_telegram(chave)
                removidas += 1
                c.execute(
                    "UPDATE protection_alvos SET status = 'removido'"
                    " WHERE scan_id = ? AND chave = ?", (str(scan_id), chave),
                )
            except Exception as e:  # noqa: BLE001 - registra e continua o lote
                log.warning("Proteção: falha ao remover %s: %s", chave, e)
                c.execute(
                    "UPDATE protection_alvos SET status = 'falhou'"
                    " WHERE scan_id = ? AND chave = ?", (str(scan_id), chave),
                )
        c.execute(
            "UPDATE protection_scans SET status = 'concluido', confirmado_em = ?"
            " WHERE id = ?",
            (dt.datetime.now().isoformat(timespec="seconds"), str(scan_id)),
        )
    log.info("Proteção %s: %d fonte(s) removida(s)", scan_id, removidas)
    resultado = obter_scan(scan_id) or {}
    resultado["removidas"] = removidas
    return resultado


def cancelar(scan_id: str) -> dict:
    scan = obter_scan(scan_id)
    if not scan:
        raise ErroProtecao("Scan não encontrado.")
    if scan["status"] != "revisao":
        raise ErroProtecao("Este scan já foi concluído ou cancelado.")
    with conn() as c:
        c.execute("UPDATE protection_scans SET status = 'cancelado' WHERE id = ?",
                  (str(scan_id),))
        c.execute(
            "UPDATE protection_alvos SET status = 'cancelado'"
            " WHERE scan_id = ? AND status = 'pendente'", (str(scan_id),),
        )
    return obter_scan(scan_id) or {}
