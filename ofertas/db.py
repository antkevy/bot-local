import datetime as dt
import os
import sqlite3

from .config import DATA_DIR
from .models import Oferta

# Nome público de propósito. As três suítes manuais redirecionam o banco com
# `db.DB_PATH = <temporário>` believing que assim ficam isoladas; enquanto esta
# variável se chamava `_DB`, essa troca não fazia nada e elas gravavam — e
# apagavam — linhas do banco de verdade a cada execução. Um teste novo
# (tests/test_isolamento_dados.py) falha se o banco real for tocado.
DB_PATH = DATA_DIR / "ofertas.db"

_COLUNAS = (
    "uid TEXT PRIMARY KEY,"
    " plataforma TEXT,"
    " titulo TEXT,"
    " preco REAL,"
    " url_afiliado TEXT,"
    " imagem TEXT,"
    " postada_em TEXT"
)

_COLUNAS_FONTES = (
    "chat_id TEXT PRIMARY KEY,"
    " nome TEXT,"
    " tipo TEXT,"
    " ativa INTEGER DEFAULT 1,"
    " adicionada_em TEXT,"
    " ultima_msg_id INTEGER DEFAULT 0,"
    " ultimo_processamento TEXT"
)

_COLUNAS_MSGS = (
    "source_id TEXT,"
    " message_id INTEGER,"
    " processada_em TEXT,"
    " uid TEXT,"
    " status TEXT,"
    " PRIMARY KEY(source_id, message_id)"
)

_COLUNAS_PENDENTES_ML = (
    "uid TEXT PRIMARY KEY,"
    " url_produto TEXT,"
    " titulo TEXT,"
    " preco REAL,"
    " preco_original REAL,"
    " desconto INTEGER,"
    " imagem TEXT,"
    " cupom TEXT,"
    " beneficio_cupom TEXT,"
    " tipo TEXT,"
    " raw_data TEXT,"
    " adicionada_em TEXT,"
    " status TEXT"
)
# Tentativas e último erro das pendências do ML. Antes, uma oferta que não
# conseguisse ser publicada era apagada da tabela sem dejar rastro, e a
# pendência sumia sem nunca ter saído. Com estas colunas dá para ver o que
# travou e quantas vezes.
_COLUNAS_PENDENTES_ML_EXTRA = (
    "tentativas INTEGER DEFAULT 0",
    "ultimo_erro TEXT",
    "ultima_tentativa_em TEXT",
)

# Reserva de uma oferta que já passou pelos filtros e está a caminho da
# publicação. Sem ela, `ja_postada` e `registrar` ficavam separados por todo o
# trabalho caro do meio (gerar link no Playwright, normalizar com o Grok,
# esperar o intervalo de velocidade): durante essa janela outro processo
# consultava `ja_postada`, via a mesma oferta, e publicava em duplicidade.
_COLUNAS_RESERVAS = (
    "uid TEXT PRIMARY KEY,"
    " reservado_em TEXT,"
    " pid INTEGER"
)

# Tempo máximo que uma reserva vale sem o dono se-renovar. Nunca é o
# mecanismo principal de expiração: um processo que morre libera a reserva na
# hora (o PID não existe mais) e o TTL cobre só o dono que ficou pendurado.
TTL_RESERVA_SEGUNDOS = 3600


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS postadas (" + _COLUNAS + ")")
    c.execute("CREATE TABLE IF NOT EXISTS fontes_telegram (" + _COLUNAS_FONTES + ")")
    c.execute("CREATE TABLE IF NOT EXISTS mensagens_telegram (" + _COLUNAS_MSGS + ")")
    c.execute("CREATE TABLE IF NOT EXISTS ofertas_pendentes_ml (" + _COLUNAS_PENDENTES_ML + ")")
    c.execute("CREATE TABLE IF NOT EXISTS reservas (" + _COLUNAS_RESERVAS + ")")
    # O painel e o bot agora escrevem no mesmo arquivo ao mesmo tempo (a trava
    # de instância reduz a concorrência, mas não elimina: o painel grava
    # fontes/cadência enquanto o bot reserva ofertas). Sem espera, um deles
    # levaria "database is locked" e a reserva se perderia — justamente o que
    # abriria brecha para o post duplicado. Não usamos WAL de propósito: ele
    # criaria arquivos .db-wal/.db-shm novos no banco do usuário.
    c.execute("PRAGMA busy_timeout=5000")
    # Bancos criados por versões antigas não têm url_afiliado/imagem/url_produto;
    # adiciona sem perder dados. `url_produto` (link original) não entra em
    # _COLUNAS de propósito: é o ALTER abaixo que garante a coluna em bancos
    # novos E antigos, num só caminho.
    existentes = {r[1] for r in c.execute("PRAGMA table_info(postadas)")}
    for coluna in ("url_afiliado", "imagem", "url_produto"):
        if coluna not in existentes:
            try:
                c.execute(f"ALTER TABLE postadas ADD COLUMN {coluna} TEXT")
            except sqlite3.OperationalError:
                pass
    # Mesma ideia para as pendências do ML.
    existentes = {r[1] for r in c.execute("PRAGMA table_info(ofertas_pendentes_ml)")}
    for coluna in _COLUNAS_PENDENTES_ML_EXTRA:
        nome = coluna.split()[0]
        if nome not in existentes:
            try:
                c.execute(f"ALTER TABLE ofertas_pendentes_ml ADD COLUMN {coluna}")
            except sqlite3.OperationalError:
                pass
    c.commit()
    return c


def init_db() -> None:
    """Inicializa as tabelas do banco de dados SQLite."""
    with _conn():
        pass


def ja_postada(uid: str, dentro_de_dias: int) -> bool:
    with _conn() as c:
        row = c.execute("SELECT postada_em FROM postadas WHERE uid = ?", (uid,)).fetchone()
    if not row:
        return False
    try:
        postada = dt.datetime.fromisoformat(row[0])
    except ValueError:          # registro antigo com data inválida: não bloqueia a postagem
        return False
    return (dt.datetime.now() - postada) < dt.timedelta(days=dentro_de_dias)


def registrar(oferta: Oferta) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO postadas"
            " (uid, plataforma, titulo, preco, url_afiliado, imagem,"
            "  postada_em, url_produto)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (oferta.uid, oferta.plataforma, oferta.titulo, oferta.preco,
             oferta.url_afiliado, oferta.imagem,
             dt.datetime.now().isoformat(timespec="seconds"),
             oferta.url_produto),
        )
        # A reserva virou postagem: some na mesma transação, senão a oferta fica
        # travada até o TTL.
        c.execute("DELETE FROM reservas WHERE uid = ?", (oferta.uid,))


# ── Reservas (fecha a janela entre checar e registrar) ─────────────────

def _reserva_ativa(linha, agora: dt.datetime, ttl: int) -> bool:
    """A linha de reserva ainda vale? Considera dono morto e TTL vencido."""
    if not linha:
        return False
    _uid, reservado_em, pid = linha
    if pid:
        # Dono que não existe mais: a reserva é liberada na hora, para uma
        # queda no meio da publicação não travar a oferta por uma hora.
        from .instancia import processo_vivo
        if not processo_vivo(pid):
            return False
    try:
        quando = dt.datetime.fromisoformat(reservado_em)
    except (TypeError, ValueError):
        return False
    return (agora - quando) < dt.timedelta(seconds=ttl)


def reservar(uid: str, ttl: int = TTL_RESERVA_SEGUNDOS) -> bool:
    """Toma a oferta para este processo. True se ninguém a tinha reservado.

    Incorpora o PID de quem reservou: se esse processo morrer, a reserva é
    liberada na próxima consulta, sem esperar o TTL.
    """
    agora = dt.datetime.now()
    with _conn() as c:
        c.execute("BEGIN IMMEDIATE")
        linha = c.execute("SELECT uid, reservado_em, pid FROM reservas WHERE uid = ?",
                          (uid,)).fetchone()
        if _reserva_ativa(linha, agora, ttl):
            return False
        c.execute(
            "INSERT INTO reservas (uid, reservado_em, pid) VALUES (?, ?, ?)"
            " ON CONFLICT(uid) DO UPDATE SET"
            " reservado_em = excluded.reservado_em, pid = excluded.pid",
            (uid, agora.isoformat(timespec="seconds"), os.getpid()),
        )
    return True


def liberar_reserva(uid: str) -> None:
    """Devolve a oferta ao limbo (a publicação não aconteceu)."""
    with _conn() as c:
        c.execute("DELETE FROM reservas WHERE uid = ?", (uid,))


def esta_reservada(uid: str, ttl: int = TTL_RESERVA_SEGUNDOS) -> bool:
    agora = dt.datetime.now()
    with _conn() as c:
        linha = c.execute("SELECT uid, reservado_em, pid FROM reservas WHERE uid = ?",
                          (uid,)).fetchone()
        ativa = _reserva_ativa(linha, agora, ttl)
        if linha and not ativa:
            c.execute("DELETE FROM reservas WHERE uid = ?", (uid,))
    return ativa


def ja_ou_reservada(uid: str, dentro_de_dias: int,
                    ttl: int = TTL_RESERVA_SEGUNDOS) -> bool:
    """A oferta já foi postada, ou está sendo postada agora por alguém?"""
    return ja_postada(uid, dentro_de_dias) or esta_reservada(uid, ttl)


def limpar_reservas_vencidas(ttl: int = TTL_RESERVA_SEGUNDOS) -> int:
    """Apaga reservas cujo dono morreu ou cujo TTL venceu. Devolve quantas saiu."""
    agora = dt.datetime.now()
    with _conn() as c:
        linhas = c.execute("SELECT uid, reservado_em, pid FROM reservas").fetchall()
        mortas = [ln[0] for ln in linhas if not _reserva_ativa(ln, agora, ttl)]
        for uid in mortas:
            c.execute("DELETE FROM reservas WHERE uid = ?", (uid,))
    return len(mortas)


def total_reservadas() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM reservas").fetchone()[0]


def total_postadas() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM postadas").fetchone()[0]


def listar_postadas(limite: int = 50) -> list[dict]:
    with _conn() as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT uid, plataforma, titulo, preco, url_afiliado, imagem,"
            "       postada_em, url_produto"
            " FROM postadas ORDER BY postada_em DESC LIMIT ?",
            (limite,),
        ).fetchall()
        return [dict(r) for r in rows]


def contar_por_plataforma() -> dict[str, int]:
    with _conn() as c:
        rows = c.execute(
            "SELECT plataforma, COUNT(*) FROM postadas GROUP BY plataforma"
        ).fetchall()
        return {p: cnt for p, cnt in rows}


def posts_por_dias(dias: int = 7) -> list[int]:
    """Quantidade de postagens em cada um dos últimos N dias (hoje por último)."""
    hoje = dt.date.today()
    dias_lista = [hoje - dt.timedelta(days=i) for i in range(dias - 1, -1, -1)]
    contagem = {d: 0 for d in dias_lista}
    with _conn() as c:
        for (postada_em,) in c.execute("SELECT postada_em FROM postadas"):
            try:
                d = dt.datetime.fromisoformat(postada_em).date()
            except (ValueError, TypeError):
                continue
            if d in contagem:
                contagem[d] += 1
    return [contagem[d] for d in dias_lista]


def total_em(dias: int) -> int:
    """Postagens feitas nos últimos N dias (inclui hoje)."""
    return sum(posts_por_dias(dias))


# ── Scraping de Telegram (Deduplicação e Fontes) ─────────────────────

def ja_processada_msg_telegram(source_id: str | int, message_id: int) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM mensagens_telegram WHERE source_id = ? AND message_id = ?",
            (str(source_id), int(message_id)),
        ).fetchone()
        return bool(row)


def marcar_ultima_mensagem_fonte(chat_id: str | int, message_id: int) -> None:
    """Registra que a fonte já viu a mensagem `message_id`.

    Precisa ser uma função própria, e não o `atualizar_status_fonte_telegram`:
    aquele muda a flag `ativa` e o userbot o chamava com o id da mensagem no
    lugar do booleano, o que não marcava nada e ainda podia reativar uma
    fonte que o dono tinha desligado. O `chat_id` tem de ser a chave como
    ela está cadastrada — se a fonte foi salva como "@nerdofertas", é
    "@nerdofertas" que o UPDATE precisa encontrar.
    """
    with _conn() as c:
        c.execute(
            "UPDATE fontes_telegram"
            " SET ultima_msg_id = MAX(ultima_msg_id, ?), ultimo_processamento = ?"
            " WHERE chat_id = ?",
            (int(message_id), dt.datetime.now().isoformat(timespec="seconds"), str(chat_id)),
        )


def registrar_msg_telegram(source_id: str | int, message_id: int, uid: str = "", status: str = "ok") -> None:
    agora = dt.datetime.now().isoformat(timespec="seconds")
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO mensagens_telegram"
            " (source_id, message_id, processada_em, uid, status)"
            " VALUES (?, ?, ?, ?, ?)",
            (str(source_id), int(message_id), agora, uid, status),
        )
    marcar_ultima_mensagem_fonte(source_id, message_id)


def listar_fontes_telegram(ativas_apenas: bool = False) -> list[dict]:
    """Lista as fontes do Telegram. Por padrão, todas.

    `ativas_apenas` existia nos chamadores (`telegram_userbot.py`) sem existir
    aqui: a chamada levantava TypeError, e o monitor do userbot morria no
    startup — dentro de um `except` genérico que registrava só um aviso
    "Não foi possível iniciar o Telethon Userbot", sem dizer que era um erro
    de código e não de configuração.
    """
    with _conn() as c:
        c.row_factory = sqlite3.Row
        sql = "SELECT * FROM fontes_telegram"
        if ativas_apenas:
            sql += " WHERE ativa = 1"
        sql += " ORDER BY adicionada_em DESC"
        return [dict(r) for r in c.execute(sql)]


def salvar_fonte_telegram(chat_id: str | int, nome: str, tipo: str = "canal", ativa: bool = True) -> None:
    agora = dt.datetime.now().isoformat(timespec="seconds")
    with _conn() as c:
        c.execute(
            "INSERT INTO fontes_telegram (chat_id, nome, tipo, ativa, adicionada_em, ultima_msg_id, ultimo_processamento)"
            " VALUES (?, ?, ?, ?, ?, 0, ?)"
            " ON CONFLICT(chat_id) DO UPDATE SET"
            " nome = excluded.nome,"
            " tipo = excluded.tipo,"
            " ativa = excluded.ativa",
            (str(chat_id), nome, tipo, 1 if ativa else 0, agora, agora),
        )


def remover_fonte_telegram(chat_id: str | int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM fontes_telegram WHERE chat_id = ?", (str(chat_id),))


def atualizar_status_fonte_telegram(chat_id: str | int, ativa: bool) -> None:
    with _conn() as c:
        c.execute("UPDATE fontes_telegram SET ativa = ? WHERE chat_id = ?", (1 if ativa else 0, str(chat_id)))


def total_msgs_telegram_processadas() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM mensagens_telegram").fetchone()[0]


def salvar_oferta_pendente_ml(oferta: Oferta, status: str = "aguardando_autenticacao") -> None:
    agora = dt.datetime.now().isoformat(timespec="seconds")
    with _conn() as c:
        c.execute(
            "INSERT INTO ofertas_pendentes_ml (uid, url_produto, titulo, preco, preco_original, desconto, imagem, cupom, beneficio_cupom, tipo, raw_data, adicionada_em, status)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(uid) DO UPDATE SET"
            " url_produto = excluded.url_produto,"
            " titulo = excluded.titulo,"
            " preco = excluded.preco,"
            " preco_original = excluded.preco_original,"
            " desconto = excluded.desconto,"
            " imagem = excluded.imagem,"
            " cupom = excluded.cupom,"
            " beneficio_cupom = excluded.beneficio_cupom,"
            " tipo = excluded.tipo,"
            " status = excluded.status",
            (
                oferta.uid,
                oferta.url_produto,
                oferta.titulo,
                oferta.preco,
                oferta.preco_original,
                oferta.desconto,
                oferta.imagem,
                oferta.cupom,
                oferta.beneficio_cupom,
                oferta.tipo,
                oferta.extra or "",
                agora,
                status,
            ),
        )


def listar_ofertas_pendentes_ml(status: str | None = None) -> list[dict]:
    with _conn() as c:
        c.row_factory = sqlite3.Row
        if status:
            rows = c.execute("SELECT * FROM ofertas_pendentes_ml WHERE status = ? ORDER BY adicionada_em ASC", (status,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM ofertas_pendentes_ml ORDER BY adicionada_em ASC").fetchall()
        return [dict(r) for r in rows]


def remover_oferta_pendente_ml(uid: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM ofertas_pendentes_ml WHERE uid = ?", (uid,))


def marcar_tentativa_pendente_ml(uid: str, erro: str = "") -> None:
    """Registra que a publicação da pendência falhou, e a MANTÉM na tabela.

    A oferta só é removida quando foi realmente publicada (ou quando já tinha
    sido postada por outro caminho). Antes ela era apagada em qualquer
    desfecho — inclusive quando faltava link de afiliado, quando os filtros
    recusavam ou quando o envio ao Telegram falhava — e a oportunidade se
    perdia em silêncio, sem log e sem chance de recovery.
    """
    with _conn() as c:
        c.execute(
            "UPDATE ofertas_pendentes_ml SET"
            " tentativas = COALESCE(tentativas, 0) + 1,"
            " ultimo_erro = ?,"
            " ultima_tentativa_em = ?"
            " WHERE uid = ?",
            (erro[:500], dt.datetime.now().isoformat(timespec="seconds"), uid),
        )


def total_tentativas_pendentes_ml(uid: str) -> int:
    with _conn() as c:
        row = c.execute("SELECT tentativas FROM ofertas_pendentes_ml WHERE uid = ?",
                        (uid,)).fetchone()
    return int((row[0] if row else 0) or 0)


def total_ofertas_pendentes_ml() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM ofertas_pendentes_ml").fetchone()[0]

