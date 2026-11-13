"""Rotas dos recursos extras, isoladas do restante do painel.

`painel.py` tem um único `do_GET`/`do_POST` com uma cadeia enorme de `elif`.
Em vez de espalhar seis recursos novos por dentro dela, o painel delega para
cá o que não conhece. Assim:

- o pipeline e as rotas existentes não mudam;
- cada recurso só responde quando `config.yaml -> extras.<nome>` está ligado;
- os erros de validação (mensagens em português, prontas para a tela) saem
  como 400, e recurso desligado sai como 404 — não como 500.

O contrato imita o do ScanHub onde faz sentido: `POST /api/mirrors` +
`/api/mirrors/<id>/toggle`, `POST /api/broadcasts` com `kind`, e o fluxo de
proteção em três passos (scan -> revisão -> confirm/cancel).
"""
from __future__ import annotations

import re

from . import broadcasts, credentials, mirrors, protection, smartlink, watermark
from . import config as _config_mod
from .extra_db import init_db

_ROTAS_PROTECAO = re.compile(r"^/api/protection/scans/([A-Za-z0-9_-]+)(?:/(confirm|cancel))?$")
_ROTAS_MIRRORS = re.compile(r"^/api/mirrors/(\d+)/(toggle|remove)$")
_ROTAS_DISPAROS = re.compile(r"^/api/broadcasts/(\d+)/cancelar$")
_ROTAS_SMART = re.compile(r"^/api/smart-link/([A-Za-z0-9_-]+)/remove$")
_SLUG_SEGURO = re.compile(r"^[A-Za-z0-9_-]{3,32}$")

# Recurso -> flag em config.yaml. `extras` (metadados) fica fora de propósito:
# a tela precisa conseguir listar as chaves mesmo com tudo desligado.
_FLAGS = {
    "mirrors": "extras_espelhamento",
    "broadcasts": "extras_disparos",
    "protection": "extras_protecao",
    "watermark": "extras_marca_dagua",
    "smart-link": "extras_smart_link",
    "credentials": "extras_credenciais",
}


def _cfg():
    return _config_mod.config


def _ligado(recurso: str) -> bool:
    return bool(getattr(_cfg(), _FLAGS[recurso], False))


def _flags() -> dict:
    cfg = _cfg()
    return {
        "espelhamento": bool(cfg.extras_espelhamento),
        "disparos": bool(cfg.extras_disparos),
        "protecao": bool(cfg.extras_protecao),
        "marca_dagua": bool(cfg.extras_marca_dagua),
        "smart_link": bool(cfg.extras_smart_link),
        "credenciais": bool(cfg.extras_credenciais),
        "disparos_horario_silencio": cfg.disparos_horario_silencio,
    }


def _desligado(recurso: str):
    return {"erro": f"Recurso '{recurso}' desligado em config.yaml (extras)."}, 404


def _pegar(dados: dict, *nomes, padrao=None):
    for nome in nomes:
        if nome in dados:
            return dados[nome]
    return padrao


def _erro_validacao(e: ValueError):
    return {"erro": str(e)}, 400


# ── GET ────────────────────────────────────────────────────────────────

def tratar_get(rota: str, _query: str = ""):
    """(payload, status) para a rota, ou None se não é nossa."""
    if rota == "/api/extras":
        return {"flags": _flags()}, 200

    if rota == "/api/mirrors":
        if not _ligado("mirrors"):
            return _desligado("espelhamento")
        return {"mirrors": mirrors.listar(),
                "destinos": mirrors.destinos_ativos()}, 200

    if rota == "/api/broadcasts":
        if not _ligado("broadcasts"):
            return _desligado("disparos")
        return {"broadcasts": broadcasts.listar(),
                "horario_silencio": _cfg().disparos_horario_silencio}, 200

    if rota == "/api/protection/scans":
        if not _ligado("protection"):
            return _desligado("protecao")
        return {"scans": protection.listar_scans()}, 200

    if rota in ("/api/watermark",):
        if not _ligado("watermark"):
            return _desligado("marca_dagua")
        return {"config": watermark.obter(), "presets": list(watermark.PRESETS)}, 200

    if rota == "/api/smart-link/overview":
        if not _ligado("smart-link"):
            return _desligado("smart_link")
        return smartlink.overview(), 200

    if rota == "/api/credentials":
        if not _ligado("credentials"):
            return _desligado("credenciais")
        return {"credenciais": credentials.status()}, 200

    m = _ROTAS_PROTECAO.match(rota)
    if m:
        if m.group(2):
            return None
        if not _ligado("protection"):
            return _desligado("protecao")
        scan = protection.obter_scan(m.group(1))
        if not scan:
            return {"erro": "Scan não encontrado."}, 404
        return scan, 200

    return None


# ── POST ───────────────────────────────────────────────────────────────

def tratar_post(rota: str, dados: dict):
    """(payload, status) para a rota, ou None se não é nossa."""
    if rota == "/api/extras/config":
        return _salvar_flags(dados)

    if rota == "/api/mirrors":
        if not _ligado("mirrors"):
            return _desligado("espelhamento")
        try:
            return mirrors.adicionar(
                _pegar(dados, "chat_id", "destino", padrao=""),
                _pegar(dados, "nome", padrao=""),
            ), 201
        except ValueError as e:
            return _erro_validacao(e)

    m = _ROTAS_MIRRORS.match(rota)
    if m:
        if not _ligado("mirrors"):
            return _desligado("espelhamento")
        if m.group(2) == "toggle":
            linha = mirrors.alternar(int(m.group(1)),
                                     bool(_pegar(dados, "enabled", "ativo", padrao=True)))
            if not linha:
                return {"erro": "Espelho não encontrado."}, 404
            return linha, 200
        return ({"ok": True} if mirrors.remover(int(m.group(1)))
                else {"erro": "Espelho não encontrado."}), 200

    if rota == "/api/broadcasts":
        if not _ligado("broadcasts"):
            return _desligado("disparos")
        try:
            return broadcasts.criar(
                kind=_pegar(dados, "kind", "tipo", padrao="message"),
                texto=_pegar(dados, "texto", "text", padrao=""),
                destinos=_pegar(dados, "destinos", "groupIds", padrao=[]),
                imagem=_pegar(dados, "imagem", "image", padrao=""),
                agendado_para=_pegar(dados, "agendado_para", "scheduledAt", padrao=""),
                ritmo_segundos=_pegar(dados, "ritmo_segundos", "pace", padrao=3),
                pergunta=_pegar(dados, "pergunta", "question", padrao=""),
                opcoes=_pegar(dados, "opcoes", "options", padrao=[]),
                multipla=bool(_pegar(dados, "multipla", "multi", padrao=False)),
                fecha_em=_pegar(dados, "fecha_em", "closesAt", padrao=""),
            ), 201
        except ValueError as e:
            return _erro_validacao(e)

    m = _ROTAS_DISPAROS.match(rota)
    if m:
        if not _ligado("broadcasts"):
            return _desligado("disparos")
        if not broadcasts.cancelar(int(m.group(1))):
            return {"erro": "Disparo não encontrado ou já enviado."}, 404
        return {"ok": True}, 200

    if rota == "/api/protection/scans":
        if not _ligado("protection"):
            return _desligado("protecao")
        try:
            return protection.iniciar_scan(
                _pegar(dados, "dias", "days", padrao=protection.DIAS_PADRAO)), 201
        except ValueError as e:
            return _erro_validacao(e)

    m = _ROTAS_PROTECAO.match(rota)
    if m:
        if not _ligado("protection"):
            return _desligado("protecao")
        scan_id, acao = m.group(1), m.group(2)
        if not acao:
            return {"erro": "Rota desconhecida."}, 404
        try:
            if acao == "confirm":
                chaves = _pegar(dados, "chaves", "keys", padrao=[])
                return protection.confirmar(scan_id, chaves), 200
            return protection.cancelar(scan_id), 200
        except ValueError as e:
            return _erro_validacao(e)

    if rota == "/api/watermark":
        if not _ligado("watermark"):
            return _desligado("marca_dagua")
        try:
            return watermark.configurar(
                preset=_pegar(dados, "preset", padrao="final"),
                handle=_pegar(dados, "handle", padrao=""),
                ativo=bool(_pegar(dados, "ativo", "enabled", padrao=True)),
            ), 200
        except ValueError as e:
            return _erro_validacao(e)

    if rota == "/api/smart-link":
        if not _ligado("smart-link"):
            return _desligado("smart_link")
        try:
            return smartlink.criar(
                url=_pegar(dados, "url", padrao=""),
                plataforma=_pegar(dados, "plataforma", "platform", padrao=""),
                slug=_pegar(dados, "slug", "apelido", padrao=""),
            ), 201
        except ValueError as e:
            return _erro_validacao(e)

    m = _ROTAS_SMART.match(rota)
    if m:
        if not _ligado("smart-link"):
            return _desligado("smart_link")
        return ({"ok": True} if smartlink.remover(m.group(1))
                else {"erro": "Link não encontrado."}), 200

    if rota == "/api/credentials":
        if not _ligado("credentials"):
            return _desligado("credenciais")
        plataforma = _pegar(dados, "plataforma", "platform", padrao="")
        try:
            if _pegar(dados, "remover", padrao=False):
                return ({"ok": True} if credentials.remover(plataforma)
                        else {"erro": "Credencial não encontrada."}), 200
            return credentials.definir(
                plataforma, _pegar(dados, "segredo", "secret", padrao="")), 200
        except ValueError as e:
            return _erro_validacao(e)

    return None


def tratar_smartlink(slug: str) -> str | None:
    """Resolve `/s/<slug>` e conta o clique. Não exige feature ligada: um link
    já criado continua valendo mesmo que o recurso seja desligado depois."""
    if not _SLUG_SEGURO.match(str(slug or "")):
        return None
    return smartlink.resolver(str(slug))


def _salvar_flags(dados: dict):
    """Liga/desliga recursos no config.yaml, com validação da janela."""
    novo = {}
    for chave in ("espelhamento", "disparos", "protecao", "marca_dagua",
                  "smart_link", "credenciais"):
        if chave in dados:
            novo[chave] = bool(dados[chave])
    if "disparos_horario_silencio" in dados:
        janela = str(dados["disparos_horario_silencio"] or "").strip()
        if janela and not re.fullmatch(
                r"([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d", janela):
            return {"erro": "O horário de silêncio precisa ser HH:MM-HH:MM."}, 400
        novo["disparos_horario_silencio"] = janela
    _config_mod.salvar_yaml_secao("extras", novo)
    init_db()
    return {"ok": True, "flags": _flags()}, 200
