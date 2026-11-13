"""Disparos: mensagens e enquetes agendadas com ritmo e horário de silêncio.

O ScanHub tinha uma tabela só para os dois tipos (`kind: message | poll`) e
mandava `pace` junto com o agendamento. Replicamos o contrato:

    criar(kind="message", texto="...", destinos=["@canal"], agendado_para="...",
          ritmo_segundos=3)
    criar(kind="poll", pergunta="...", opcoes=["A", "B"], multipla=False)

O envio de verdade é uma função assíncrona separada (`enviar_pendentes`) para
o módulo continuar testável sem rede: o relógio, o horário de silêncio e a
ordem dos disparos são lógica pura.

Opt-in: nada aqui roda sozinho. Enquanto `extras.disparos` estiver falso no
config.yaml, o painel recusa as rotas e nenhum agendamento é lido.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import sqlite3

from .config import agora_brt
from .extra_db import conn

log = logging.getLogger("ofertas.broadcasts")

KINDS = ("message", "poll")
STATUS = ("pendente", "enviado", "erro", "cancelado")
RITMO_MAXIMO = 3600


class ErroDisparo(ValueError):
    """Erro de validação com mensagem pronta para a tela."""


def _json_lista(valor) -> list[str]:
    if isinstance(valor, str):
        try:
            valor = json.loads(valor)
        except ValueError:
            return []
    if not isinstance(valor, (list, tuple)):
        return []
    return [str(v).strip() for v in valor if str(v).strip()]


def _parse_data(valor) -> dt.datetime | None:
    """Aceita ISO com T, com espaço e sem segundos. Devolve hora de parede BRT."""
    texto = str(valor or "").strip()
    if not texto:
        return None
    for formato in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M",
                    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(texto, formato)
        except ValueError:
            continue
    raise ErroDisparo("Data inválida: use AAAA-MM-DD HH:MM.")


def _formatar_data(d: dt.datetime | None) -> str:
    return d.strftime("%Y-%m-%dT%H:%M") if d else ""


def em_horario_silencio(agora: dt.datetime | None = None,
                        janela: str | None = None) -> bool:
    """True se `agora` cai dentro do horário de silêncio configurado.

    A janela é escrita em BRT, no mesmo formato do horário ativo do bot
    ("22:00-08:00"), e aceita virada de meia-noite. Formato inválido não
    bloqueia — silêncio acidental é pior do que disparo na hora errada?
    Não: um formato quebrado travando tudo é o que faz o usuário desligar o
    recurso. Por isso inválido = sem silêncio, e o painel valida na borda.
    """
    from . import config as _config_mod
    janela = (janela if janela is not None
              else getattr(_config_mod.config, "disparos_horario_silencio", ""))
    janela = str(janela or "").strip()
    if not janela:
        return False
    try:
        inicio, fim = janela.split("-")
        h1, m1 = (int(x) for x in inicio.strip().split(":"))
        h2, m2 = (int(x) for x in fim.strip().split(":"))
    except (ValueError, TypeError):
        return False
    if agora is None:
        agora = agora_brt()
    t, a, b = agora.hour * 60 + agora.minute, h1 * 60 + m1, h2 * 60 + m2
    return a <= t < b if a <= b else (t >= a or t < b)


def criar(kind: str = "message", texto: str = "", destinos=None,
          imagem: str = "", agendado_para=None, ritmo_segundos: int = 3,
          pergunta: str = "", opcoes=None, multipla: bool = False,
          fecha_em=None, agora: dt.datetime | None = None) -> dict:
    """Valida e grava um disparo. Devolve a linha criada."""
    kind = str(kind or "").strip().lower()
    if kind not in KINDS:
        raise ErroDisparo("Tipo inválido: use 'message' ou 'poll'.")

    destinos = _json_lista(destinos)
    if not destinos:
        raise ErroDisparo("Escolha ao menos um destino para o disparo.")

    if kind == "message":
        if not str(texto or "").strip():
            raise ErroDisparo("A mensagem não pode ficar vazia.")
        pergunta, opcoes = "", []
    else:
        texto = str(pergunta or texto or "").strip()
        pergunta = texto
        opcoes = _json_lista(opcoes)
        if not pergunta:
            raise ErroDisparo("A enquete precisa de uma pergunta.")
        if not 2 <= len(opcoes) <= 10:
            raise ErroDisparo("A enquete precisa de 2 a 10 opções.")
        texto = pergunta

    if not isinstance(ritmo_segundos, (int, float)) or int(ritmo_segundos) < 0:
        raise ErroDisparo("O ritmo não pode ser negativo.")
    ritmo = min(int(ritmo_segundos), RITMO_MAXIMO)

    agendado = _parse_data(agendado_para)
    fecha = _parse_data(fecha_em)
    agora = agora or agora_brt()
    if agendado and agendado < agora - dt.timedelta(minutes=1):
        raise ErroDisparo("O agendamento está no passado.")

    criado = agora.isoformat(timespec="seconds")
    with conn() as c:
        cur = c.execute(
            "INSERT INTO broadcasts (kind, texto, imagem, destinos,"
            " agendado_para, ritmo_segundos, pergunta, opcoes, multipla,"
            " fecha_em, status, criado_em)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendente', ?)",
            (kind, texto, str(imagem or "").strip() or None,
             json.dumps(destinos, ensure_ascii=False), _formatar_data(agendado),
             ritmo, pergunta, json.dumps(opcoes, ensure_ascii=False),
             1 if multipla else 0, _formatar_data(fecha), criado),
        )
        c.row_factory = sqlite3.Row
        linha = c.execute("SELECT * FROM broadcasts WHERE id = ?",
                          (cur.lastrowid,)).fetchone()
    log.info("Disparo %s criado (%s) para %s", cur.lastrowid, kind, destinos)
    return _dict(linha)


def listar(status: str | None = None) -> list[dict]:
    with conn() as c:
        c.row_factory = _linha_dict
        if status:
            linhas = c.execute(
                "SELECT * FROM broadcasts WHERE status = ? ORDER BY id DESC",
                (status,),
            ).fetchall()
        else:
            linhas = c.execute("SELECT * FROM broadcasts ORDER BY id DESC").fetchall()
    return [_dict(ln) for ln in linhas]


def cancelar(broadcast_id: int) -> bool:
    """Cancela só o que ainda não saiu. Disparo enviado não volta atrás."""
    with conn() as c:
        cur = c.execute(
            "UPDATE broadcasts SET status = 'cancelado'"
            " WHERE id = ? AND status = 'pendente'", (int(broadcast_id),),
        )
    return cur.rowcount > 0


def devidos(agora: dt.datetime | None = None) -> list[dict]:
    """Pendentes cujo horário já chegou. Silêncio não filtra aqui.

    `devidos` responde "o que está vencido"; quem decide se pode soar agora é
    `enviar_pendentes` (que respeita o horário de silêncio). Separar as duas
    perguntas é o que permite ao painel mostrar a fila durante a madrugada.
    """
    agora = agora or agora_brt()
    vencidos = []
    for b in listar("pendente"):
        quando = _parse_data(b["agendado_para"]) if b["agendado_para"] else None
        if quando is None or quando <= agora:
            vencidos.append(b)
    return vencidos


def marcar_enviado(broadcast_id: int, erro: str = "") -> None:
    with conn() as c:
        c.execute(
            "UPDATE broadcasts SET status = 'enviado', enviado_em = ?, erro = ?"
            " WHERE id = ?",
            (agora_brt().isoformat(timespec="seconds"), (erro or "")[:500],
             int(broadcast_id)),
        )


def marcar_erro(broadcast_id: int, erro: str) -> None:
    with conn() as c:
        c.execute("UPDATE broadcasts SET status = 'erro', erro = ? WHERE id = ?",
                  ((erro or "")[:500], int(broadcast_id)))


async def enviar_pendentes(bot, agora: dt.datetime | None = None,
                           dormir=None) -> list[dict]:
    """Envia os disparos vencidos, um destino de cada vez, no ritmo pedido.

    Devolve o resumo de cada disparo tentado. O horário de silêncio é checado
    uma vez, no começo: se está silencioso, a fila espera o próximo ciclo sem
    consumir nada. Erros são por disparo, não por lote — um destino inválido
    não pode impedir os outros de receber.
    """
    agora = agora or agora_brt()
    if em_horario_silencio(agora):
        return []
    dormir = dormir or asyncio.sleep
    resumo: list[dict] = []
    for b in devidos(agora):
        destinos = _json_lista(b.get("destinos"))
        falhas: list[str] = []
        enviados = 0
        for indice, destino in enumerate(destinos):
            try:
                await _enviar_um(bot, destino, b)
                enviados += 1
            except Exception as e:  # noqa: BLE001 - um destino não derruba o lote
                falhas.append(f"{destino}: {e}")
                log.warning("Disparo %s falhou em %s: %s", b.get("id"), destino, e)
            if indice < len(destinos) - 1 and b.get("ritmo_segundos"):
                await dormir(b["ritmo_segundos"])
        if enviados:
            marcar_enviado(b["id"], "; ".join(falhas))
        else:
            marcar_erro(b["id"], "; ".join(falhas) or "nenhum destino aceitou o envio")
        resumo.append({"id": b["id"], "enviados": enviados, "falhas": falhas})
    return resumo


async def _enviar_um(bot, destino: str, b: dict) -> None:
    if b["kind"] == "poll":
        await bot.send_poll(
            chat_id=destino, question=b["pergunta"],
            options=_json_lista(b.get("opcoes")),
            is_anonymous=True, allows_multiple_answers=bool(b.get("multipla")),
            open_period=_periodo_aberto(b.get("fecha_em")),
        )
        return
    if b.get("imagem"):
        await bot.send_photo(chat_id=destino, photo=b["imagem"], caption=b["texto"])
    else:
        await bot.send_message(chat_id=destino, text=b["texto"])


def _periodo_aberto(fecha_em) -> int | None:
    """Segundos até o fechamento da enquete (limite da API: 5..600)."""
    quando = _parse_data(fecha_em) if fecha_em else None
    if not quando:
        return None
    restante = int((quando - agora_brt()).total_seconds())
    return max(5, min(600, restante)) if restante > 0 else 5


def _linha_dict(cursor, linha):
    return dict(zip([d[0] for d in cursor.description], linha))


def _dict(linha) -> dict:
    if not linha:
        return {}
    d = dict(linha) if not isinstance(linha, dict) else dict(linha)
    d["destinos"] = _json_lista(d.get("destinos"))
    d["opcoes"] = _json_lista(d.get("opcoes"))
    d["multipla"] = bool(d.get("multipla"))
    return d
