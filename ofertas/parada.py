"""Sinal de parada cooperativa.

O ciclo roda inteiro como UM job do PTB, e a coleta acontece numa thread
(`asyncio.to_thread`). Quando o serviço recebe SIGTERM, o PTB levanta
`SystemExit` na thread principal, que desenrosca — mas o interpretador, ao
sair, espera as threads não-daemon terminarem. Sem um ponto de parada, essa
thread leva os ~10 minutos do ciclo inteiro: o `TimeoutStopSec` estoura e o
systemd mata o processo com SIGKILL no meio da coleta.

Aqui mora o `Event` que cada laço consulta entre uma página e outra. O preço
é perder as ofertas ainda não coletadas do ciclo que está abortando — que é o
preço certo: um restart não deve custar um ciclo inteiro de coleta.

O módulo é folha de propósito: `pipeline` e `sources/*` importam daqui, então
ele não pode importar nada do projeto.
"""
from __future__ import annotations

import logging
import threading

log = logging.getLogger(__name__)

_evento = threading.Event()


def pedir() -> None:
    """Avisa que o processo está encerrando. seguro chamar de qualquer thread."""
    _evento.set()


def limpar() -> None:
    """Abre uma janela nova. Só o início de um ciclo chama isto."""
    if _evento.is_set():
        log.info("Nova janela de ciclo: a parada pedida foi limpa.")
    _evento.clear()


def pedido() -> bool:
    """True se o processo está encerrando e a coleta deve ceder o caminho."""
    return _evento.is_set()


def instalar_handlers(ao_parar) -> None:
    """Assume SIGTERM/SIGINT e chama `ao_parar` antes de desenroscar.

    O PTB registraria `SIGINT/SIGTERM/SIGABRT` sozinho e levantaria
    `SystemExit` sem avisar ninguém — aí a thread da coleta só descobre que
    precisa parar quando o interpretador já está esperando por ela. Por isso o
    chamador passa `stop_signals=None` no `run_polling` e a instalação de
    sinal vira este ponto: o sinal chega, a parada é pedida, e só então o
    `SystemExit` solta a thread principal. As duas metades do problema, na
    ordem certa.
    """
    import signal

    def _handler(signum, _frame):
        nome = signal.Signals(signum).name
        log.warning("%s recebido — abortando a coleta em andamento.", nome)
        try:
            ao_parar()
        except Exception:  # noqa: BLE001
            # Um erro aqui custaria o encerramento: melhor seguir e deixar o
            # SystemExit desenroscar do que ficar pendurado esperando SIGKILL.
            log.exception("Falha ao pedir a parada cooperativa")
        raise SystemExit(128 + signum)

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _handler)
        except (OSError, ValueError) as e:
            # Sem signal.signal (thread secundária) ou sinal inexistente.
            log.debug("Não foi possível tratar %s: %s", sig, e)