"""Credenciais write-only: entram pelo painel, nunca voltam por ele.

O ScanHub expunha `secretConfigured: boolean` e um input desabilitado — o
segredo não é devolvido nem mascarado. A mesma regra aqui, e ela é o ponto do
módulo: `status()` é a única leitura pública, e `obter()` (uso interno) é a
única que devolve o valor.

O `.env` continua sendo a fonte principal das credenciais que o pipeline já
usa. Esta tabela existe para os recursos portados (ex.: tag da Amazon vinda do
painel de espelhamento), sem reescrever `.env` nem `config.py` por baixo.
"""
from __future__ import annotations

import datetime as dt
import re

from .extra_db import conn

_PLATAFORMA_VALIDA = re.compile(r"^[a-z0-9_-]{2,32}$")


class ErroCredencial(ValueError):
    """Entrada recusada com mensagem pronta para a tela."""


def _plataforma(nome: str) -> str:
    valor = str(nome or "").strip().lower()
    if not _PLATAFORMA_VALIDA.match(valor):
        raise ErroCredencial("Plataforma inválida.")
    return valor


def definir(plataforma: str, segredo: str) -> dict:
    """Grava (ou substitui) o segredo de uma plataforma. Não o devolve."""
    nome = _plataforma(plataforma)
    valor = str(segredo or "").strip()
    if not valor:
        raise ErroCredencial("O segredo não pode ficar vazio.")
    if len(valor) > 4096:
        raise ErroCredencial("O segredo é longo demais.")
    agora = dt.datetime.now().isoformat(timespec="seconds")
    with conn() as c:
        c.execute(
            "INSERT INTO credenciais (plataforma, segredo, atualizado_em)"
            " VALUES (?, ?, ?)"
            " ON CONFLICT(plataforma) DO UPDATE SET"
            " segredo = excluded.segredo,"
            " atualizado_em = excluded.atualizado_em",
            (nome, valor, agora),
        )
    return {"plataforma": nome, "secretConfigured": True, "atualizado_em": agora}


def status() -> list[dict]:
    """Só metadados: qual plataforma tem segredo e desde quando."""
    with conn() as c:
        linhas = c.execute(
            "SELECT plataforma, atualizado_em FROM credenciais ORDER BY plataforma"
        ).fetchall()
    return [{"plataforma": p, "secretConfigured": True, "atualizado_em": a}
            for p, a in linhas]


def configurada(plataforma: str) -> bool:
    try:
        nome = _plataforma(plataforma)
    except ErroCredencial:
        return False
    with conn() as c:
        return bool(c.execute(
            "SELECT 1 FROM credenciais WHERE plataforma = ?", (nome,)
        ).fetchone())


def obter(plataforma: str) -> str | None:
    """Leitura INTERNA do segredo. Nunca exponha o retorno numa rota."""
    nome = _plataforma(plataforma)
    with conn() as c:
        linha = c.execute(
            "SELECT segredo FROM credenciais WHERE plataforma = ?", (nome,)
        ).fetchone()
    return linha[0] if linha else None


def remover(plataforma: str) -> bool:
    nome = _plataforma(plataforma)
    with conn() as c:
        cur = c.execute("DELETE FROM credenciais WHERE plataforma = ?", (nome,))
    return cur.rowcount > 0
