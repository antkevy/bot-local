"""Smart links: URL curta local para um link de afiliado, com contagem.

O ScanHub expunha `POST /api/smart-link` (método passado como argumento) e
`GET /api/smart-link/overview`. Aqui o contrato é mais estreito de propósito:
criar, listar e resolver. O redirecionamento fica no painel local
(`/s/<slug>`), então nenhum serviço externo é necessário e nenhum link do
usuário sai da máquina sem ele pedir.

O slug é validado para não virar path traversal: só letras, números, `-` e `_`,
de 3 a 32 caracteres.
"""
from __future__ import annotations

import datetime as dt
import re
import secrets
import sqlite3
from urllib.parse import urlparse

from .extra_db import conn

_SLUG_VALIDO = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
_SLUG_LIMPEZA = re.compile(r"[^A-Za-z0-9_-]+")


class ErroSmartLink(ValueError):
    """Entrada recusada com mensagem pronta para a tela."""


def _validar_url(url: str) -> str:
    texto = str(url or "").strip()
    partes = urlparse(texto)
    if partes.scheme not in ("http", "https") or not partes.netloc:
        raise ErroSmartLink("Informe uma URL http(s) válida.")
    return texto


def _novo_slug() -> str:
    return secrets.token_urlsafe(6).replace("=", "").replace("-", "").replace("_", "")[:8].lower()


def criar(url: str, plataforma: str = "", slug: str = "") -> dict:
    """Cria (ou reaproveita) um smart link. Slug vazio = gerado."""
    url = _validar_url(url)
    plataforma = re.sub(r"[^a-z0-9_-]", "", str(plataforma or "").lower())[:32]
    slug = str(slug or "").strip()
    if slug:
        if not _SLUG_VALIDO.match(slug):
            raise ErroSmartLink(
                "O apelido deve ter de 3 a 32 caracteres (letras, números, - e _)."
            )
    agora = dt.datetime.now().isoformat(timespec="seconds")
    with conn() as c:
        if not slug:
            # Mesma URL já tem link: devolve o existente em vez de criar outro
            # slug para o mesmo destino.
            linha = c.execute(
                "SELECT slug, url, plataforma, cliques, criado_em"
                " FROM smart_links WHERE url = ? AND plataforma = ? LIMIT 1",
                (url, plataforma),
            ).fetchone()
            if linha:
                return _dict(linha)
        for _tentativa in range(8):
            candidato = slug or _novo_slug()
            try:
                c.execute(
                    "INSERT INTO smart_links (slug, url, plataforma, cliques, criado_em)"
                    " VALUES (?, ?, ?, 0, ?)",
                    (candidato, url, plataforma, agora),
                )
                return {"slug": candidato, "url": url, "plataforma": plataforma,
                        "cliques": 0, "criado_em": agora}
            except sqlite3.IntegrityError:
                if slug:
                    raise ErroSmartLink("Esse apelido já está em uso.")
                continue
    raise ErroSmartLink("Não consegui gerar um apelido livre; tente outro.")


def obter(slug: str) -> dict | None:
    with conn() as c:
        linha = c.execute(
            "SELECT slug, url, plataforma, cliques, criado_em"
            " FROM smart_links WHERE slug = ?", (str(slug or ""),),
        ).fetchone()
    return _dict(linha) if linha else None


def registrar_clique(slug: str) -> dict | None:
    with conn() as c:
        c.execute("UPDATE smart_links SET cliques = cliques + 1 WHERE slug = ?",
                  (str(slug or ""),))
        linha = c.execute(
            "SELECT slug, url, plataforma, cliques, criado_em"
            " FROM smart_links WHERE slug = ?", (str(slug or ""),),
        ).fetchone()
    return _dict(linha) if linha else None


def resolver(slug: str) -> str | None:
    """URL de destino e contabiliza o clique. None se o slug não existe."""
    registro = registrar_clique(slug)
    return registro["url"] if registro else None


def listar(limite: int = 100) -> list[dict]:
    with conn() as c:
        linhas = c.execute(
            "SELECT slug, url, plataforma, cliques, criado_em"
            " FROM smart_links ORDER BY criado_em DESC LIMIT ?", (int(limite),),
        ).fetchall()
    return [_dict(ln) for ln in linhas]


def remover(slug: str) -> bool:
    with conn() as c:
        cur = c.execute("DELETE FROM smart_links WHERE slug = ?", (str(slug or ""),))
    return cur.rowcount > 0


def overview() -> dict:
    with conn() as c:
        total = c.execute("SELECT COUNT(*) FROM smart_links").fetchone()[0]
        cliques = c.execute("SELECT COALESCE(SUM(cliques), 0) FROM smart_links").fetchone()[0]
    return {"total_links": int(total), "total_cliques": int(cliques),
            "links": listar()}


def _dict(linha) -> dict:
    return {"slug": linha[0], "url": linha[1], "plataforma": linha[2],
            "cliques": int(linha[3] or 0), "criado_em": linha[4]}
