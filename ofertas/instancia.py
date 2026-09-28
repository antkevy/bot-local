"""Trava de instância única: garante que só exista UM processo com cada papel.

O bot podia ser iniciado de vários lugares ao mesmo tempo — pelo painel
(`/api/start`), por `python -m ofertas run` no terminal, por `ciclo`, ou por
um segundo painel. Nenhum deles se via. Consequência prática: várias cópias
rodavam juntas, todas coletavam as mesmas ofertas, todas consultavam
`db.ja_postada()` antes de qualquer delas ter registrado o post, e todas
publicavam. É a origem dos posts repetidos.

Este módulo cria uma trava por papel (bot, painel) em `data/instancia/`.
Ao subir, o novo processo:

1. lê a trava existente;
2. se o PID registrado ainda for o mesmo processo de antes, encerra aquele
   processo (e a árvore de filhos, para matar o Chromium do Playwright junto);
3. assume a trava e passa a ser a única instância.

Identidade do processo
----------------------
Guardar só o PID não basta: o Windows recicla PIDs, e um PID reciclado
faria o novo processo matar um programa sem relação. Por isso a trava guarda
também o horário de criação do processo, lido do próprio SO (GetProcessTimes
no Windows). Só consideramos o titular vivo quando PID e horário batem.

Concorrência entre partidas
---------------------------
Dois `run` abertos no mesmo segundo poderiam ler a trava vazia e os dois
escrever. Um arquivo de reivindicação criado em exclusivo serializa o
ler->matar->gravar.
"""
from __future__ import annotations

import atexit
import errno
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .config import DATA_DIR

log = logging.getLogger("ofertas.instancia")

DIR_INSTANCIA = DATA_DIR / "instancia"

# Tempo máximo para um processoencerrado ainda em execução ser considerado
# morto pela trava.
TIMEOUT_ENCERRAMENTO_S = 10.0
# Tempo de espera pelo arquivo de reivindicação antes de desistir. Precisa ser
# bem maior que o de encerramento: a reivindicação é segurada durante o
# taskkill do processo anterior (que pode levar vários segundos), e um valor
# curto fazia o novo processo desistir e o bot não subir.
TIMEOUT_REIVINDICACAO_S = TIMEOUT_ENCERRAMENTO_S + 20.0


# ── Identidade do processo ──────────────────────────────────────────────

# Código que o Windows devolve para um processo que continua rodando.
_STILL_ACTIVE = 259


def _info_win(pid: int) -> tuple[float, int] | None:
    """(horário de criação em epoch, código de saída) do processo, ou None.

    O código de saída é o que diz se o processo ainda roda: enquanto ele
    estiver vivo o Windows devolve STILL_ACTIVE (259) e, quando morre, passa a
    devolver o código real de saída.

    Isso importa porque `OpenProcess` + `GetProcessTimes` continuam
    respondendo depois da morte do processo: medir só o horário de criação
    dava falso positivo para sempre, e a trava passava a acreditar num bot
    encerrado, deixando o novo processo batendo numa parede.

    FILETIME (100 ns desde 1601) -> epoch: dividir por 1e7 e descontar o
    deslocamento entre 1601 e 1970.
    """
    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    k32 = ctypes.windll.kernel32           # type: ignore[attr-defined]
    handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return None
    try:
        codigo = wintypes.DWORD()
        if not k32.GetExitCodeProcess(handle, ctypes.byref(codigo)):
            return None
        criacao = wintypes.FILETIME()
        saida = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        usuario = wintypes.FILETIME()
        criado_em = None
        if k32.GetProcessTimes(handle, ctypes.byref(criacao), ctypes.byref(saida),
                               ctypes.byref(kernel), ctypes.byref(usuario)):
            bruto = (criacao.dwHighDateTime << 32) | criacao.dwLowDateTime
            criado_em = (bruto / 1e7) - 11644473600.0
        return (criado_em, codigo.value)
    finally:
        k32.CloseHandle(handle)


def _info_posix(pid: int) -> tuple[float | None, bool] | None:
    """(horário de criação, ainda_ativo) no Linux/macOS, ou None se não existe."""
    try:
        with open(f"/proc/{pid}/stat", encoding="ascii") as f:
            conteudo = f.read()
    except OSError:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return None
        except PermissionError:
            return (None, True)          # existe, mas não é nosso
        return (None, True)
    campos = conteudo.rsplit(")", 1)[1].split()
    estado = campos[0]
    # Campo 22 (1-based) = starttime em ticks desde o boot.
    criado = float(campos[19]) / os.sysconf("SC_CLK_TCK")
    # 'Z' = zumbi: o processo já terminou, só não foi recolhido ainda.
    return (criado, estado != "Z")


def tempo_criacao(pid: int) -> float | None:
    """Horário de criação do processo; None quando não é possível saber."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    if sys.platform == "win32":
        info = _info_win(pid)
        return info[0] if info else None
    info = _info_posix(pid)
    return info[0] if info else None


def processo_vivo(pid: int, nascido_em: float | None = None) -> bool:
    """O PID ainda roda E é o mesmo processo de quando a trava foi gravada?

    `nascido_em` protege contra reciclagem de PID: mesmo número, processo
    diferente, então o titular da trava já não existe.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False

    if sys.platform == "win32":
        info = _info_win(pid)
        if info is None:
            # OpenProcess falhou: no Windows isso significa processo
            # inexistente (ou sem permissão). O caso comum é o primeiro, e
            # tratar como morto evita travar o bot numa trava órfã.
            return False
        criado, codigo = info
        if codigo != _STILL_ACTIVE:
            return False               # terminou: código de saída é o real
    else:
        info = _info_posix(pid)
        if info is None:
            return False
        criado, ativo = info
        if not ativo:
            return False

    if nascido_em and criado is not None:
        try:
            # 2 s de tolerância para arredondamento do FILETIME.
            if abs(criado - float(nascido_em)) > 2.0:
                return False
        except (TypeError, ValueError):
            pass
    return True


# ── Encerramento ────────────────────────────────────────────────────────

def encerrar(pid: int, arvore: bool = True) -> bool:
    """Encerra o processo (e, por padrão, os filhos). True se morreu."""
    if pid <= 0 or pid == os.getpid():
        return False
    if sys.platform == "win32":
        cmd = ["taskkill", "/PID", str(pid)]
        if arvore:
            cmd.append("/T")
        cmd.append("/F")
        try:
            subprocess.run(cmd, capture_output=True,
                           timeout=TIMEOUT_ENCERRAMENTO_S + 5)
        except subprocess.TimeoutExpired:
            # O taskkill estourou o tempo. Isso NÃO significa que o processo
            # sobreviveu: numa árvore com Chromium do Playwright ele pode
            # passar do limite e mesmo assim ter matado tudo. O veredito é de
            # aguardar_morte(), que olha o PID de verdade.
            log.debug("taskkill(%s) demorou; vou apenas esperar o processo sumir.", pid)
        except (subprocess.SubprocessError, OSError) as e:
            log.debug("taskkill(%s) falhou: %s", pid, e)
    else:
        try:
            if arvore:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError) as e:
            log.debug("SIGTERM(%s) falhou: %s", pid, e)
            return False
    return aguardar_morte(pid)


def aguardar_morte(pid: int, timeout: float = TIMEOUT_ENCERRAMENTO_S) -> bool:
    """Espera o PID sumir. True se morreu dentro do tempo."""
    limite = time.monotonic() + timeout
    while True:
        if not processo_vivo(pid):
            return True
        if time.monotonic() >= limite:
            return False
        # Poll fino: com taskkill /F a morte é quase imediata, e segurar a
        # reivindicação por mais tempo do que o necessário atrasa quem está
        # tentando subir.
        time.sleep(0.1)


# ── Arquivos ────────────────────────────────────────────────────────────

def caminho_trava(papel: str) -> Path:
    return DIR_INSTANCIA / f"{papel}.json"


def caminho_reivindicao(papel: str) -> Path:
    return DIR_INSTANCIA / f"{papel}.claim"


def ler_trava(papel: str) -> dict | None:
    """Conteúdo da trava; None se não existir, for ilegível ou estiver corrompida."""
    arq = caminho_trava(papel)
    try:
        with open(arq, encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        return None
    return dados if isinstance(dados, dict) else None


def _escrever(arq: Path, dados: dict) -> None:
    arq.parent.mkdir(parents=True, exist_ok=True)
    tmp = arq.with_suffix(arq.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    os.replace(tmp, arq)          # troca atômica: nunca lê arquivo pela metade


class _Reivindicacao:
    """Serializa o ler->matar->gravar entre processos que sobem juntos."""

    def __init__(self, papel: str):
        self.ARQ = caminho_reivindicao(papel)
        self.ok = False

    def __enter__(self) -> bool:
        self.ARQ.parent.mkdir(parents=True, exist_ok=True)
        limite = time.monotonic() + TIMEOUT_REIVINDICACAO_S
        while time.monotonic() < limite:
            try:
                fd = os.open(str(self.ARQ), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                # Reivindicação órfã de um processo que morreu no meio: se
                # ninguém a atualizar há muito tempo, é lixo e pode ir.
                try:
                    if time.time() - self.ARQ.stat().st_mtime > 60:
                        self.ARQ.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                time.sleep(0.15)
                continue
            except OSError as e:
                if e.errno == errno.EACCES:      # pragma: no cover
                    time.sleep(0.15)
                    continue
                return False
            else:
                os.write(fd, str(os.getpid()).encode("ascii"))
                os.close(fd)
                self.ok = True
                return True
        log.warning("[INSTANCIA] Não consegui reivindicar a trava a tempo.")
        return False

    def __exit__(self, *_exc) -> None:
        if self.ok:
            self.ARQ.unlink(missing_ok=True)


# ── Instância ───────────────────────────────────────────────────────────

class Instancia:
    """Trava assumida por este processo."""

    def __init__(self, papel: str, registro: dict):
        self.papel = papel
        self.registro = registro
        self.liberada = False

    @property
    def pid(self) -> int:
        return int(self.registro.get("pid", 0))

    def liberar(self) -> None:
        """Devolve a trava — só se ainda for nossa."""
        if self.liberada:
            return
        self.liberada = True
        atual = ler_trava(self.papel)
        if atual and int(atual.get("pid", 0)) != os.getpid():
            return                          # outro processo já assumiu; não mexe
        caminho_trava(self.papel).unlink(missing_ok=True)

    def __enter__(self) -> "Instancia":
        return self

    def __exit__(self, *_exc) -> None:
        self.liberar()


def _registro(papel: str) -> dict:
    return {
        "pid": os.getpid(),
        "nascido_em": tempo_criacao(os.getpid()),
        "papel": papel,
        "iniciado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "linha_comando": " ".join(sys.argv),
    }


def titular_vivo(papel: str) -> dict | None:
    """Dados da trava se o processo que a gravou ainda for o mesmo e estiver vivo."""
    dados = ler_trava(papel)
    if not dados:
        return None
    pid = dados.get("pid")
    if not processo_vivo(pid, dados.get("nascido_em")):
        return None
    return dados


def adquirir(papel: str, derrubar_anterior: bool = True,
             ao_assumir=None) -> Instancia | None:
    """Assume a trava do papel, encerrando a instância anterior se existir.

    `derrubar_anterior=False` em vez de derrubar devolve None, para o papel em
    que derrubar a instância anterior seria surpresa (o painel derrubaria o
    bot que o usuário está vendo na tela).
    """
    with _Reivindicacao(papel) as reivindicado:
        if not reivindicado:
            log.error("[INSTANCIA] Não consegui a trava de '%s': outro processo está "
                      "assume a trava neste momento. Esta instância não vai subir.", papel)
            return None
        anterior = ler_trava(papel)
        if anterior:
            pid = int(anterior.get("pid", 0) or 0)
            # `mesmo_processo` é a trava anti-suicídio: se o PID gravado for o
            # nosso, nunca chamamos encerrar() nele, venha de onde vier o
            # registro (inclusive um PID reciclado que por coincidência é o
            # nosso). Nesse caso basta sobrescrever a trava, que é o
            # comportamento desejado num re-adquirir.
            mesmo_processo = pid == os.getpid()
            vivo = processo_vivo(pid, anterior.get("nascido_em"))
            if vivo and not mesmo_processo:
                if not derrubar_anterior:
                    log.info("[INSTANCIA] Já existe um '%s' rodando (PID %s).", papel, pid)
                    return None
                log.warning("[INSTANCIA] Outro '%s' está rodando (PID %s, iniciado em %s). "
                            "Encerrando para ficar só com esta instância.",
                            papel, pid, anterior.get("iniciado_em", "?"))
                if not encerrar(pid):
                    log.error("[INSTANCIA] Não consegui encerrar o PID %s. Se ele continuar "
                              "rodando, os posts podem sair duplicados.", pid)
                elif ao_assumir:
                    ao_assumir(anterior)

        inst = Instancia(papel, _registro(papel))
        try:
            _escrever(caminho_trava(papel), inst.registro)
        except OSError as e:
            log.error("[INSTANCIA] Falha ao gravar a trava de '%s': %s", papel, e)
            return None

    atexit.register(inst.liberar)
    return inst


def limpar_trava_oufa(papel: str) -> bool:
    """Apaga a trava de um processo que não existe mais. True se removeu."""
    dados = ler_trava(papel)
    if not dados:
        return False
    if processo_vivo(dados.get("pid"), dados.get("nascido_em")):
        return False
    caminho_trava(papel).unlink(missing_ok=True)
    return True


def status(papel: str) -> dict:
    """Estado da trava de um papel, para exibir no painel."""
    dados = ler_trava(papel)
    if not dados:
        return {"ocupado": False, "pid": None}
    pid = int(dados.get("pid", 0) or 0)
    return {
        "ocupado": processo_vivo(pid, dados.get("nascido_em")),
        "pid": pid,
        "iniciado_em": dados.get("iniciado_em"),
        "linha_comando": dados.get("linha_comando", ""),
        "esta_e": pid == os.getpid(),
    }
