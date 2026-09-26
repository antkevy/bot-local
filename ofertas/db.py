import datetime as dt
import sqlite3

from .config import DATA_DIR
from .models import Oferta

_DB = DATA_DIR / "ofertas.db"

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


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB)
    c.execute("CREATE TABLE IF NOT EXISTS postadas (" + _COLUNAS + ")")
    c.execute("CREATE TABLE IF NOT EXISTS fontes_telegram (" + _COLUNAS_FONTES + ")")
    c.execute("CREATE TABLE IF NOT EXISTS mensagens_telegram (" + _COLUNAS_MSGS + ")")
    # Bancos criados por versões antigas não têm url_afiliado/imagem; adiciona sem perder dados.
    existentes = {r[1] for r in c.execute("PRAGMA table_info(postadas)")}
    for coluna in ("url_afiliado", "imagem"):
        if coluna not in existentes:
            try:
                c.execute(f"ALTER TABLE postadas ADD COLUMN {coluna} TEXT")
            except sqlite3.OperationalError:
                pass
    c.commit()
    return c


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
            " (uid, plataforma, titulo, preco, url_afiliado, imagem, postada_em)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (oferta.uid, oferta.plataforma, oferta.titulo, oferta.preco,
             oferta.url_afiliado, oferta.imagem,
             dt.datetime.now().isoformat(timespec="seconds")),
        )


def total_postadas() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM postadas").fetchone()[0]


def listar_postadas(limite: int = 50) -> list[dict]:
    with _conn() as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT uid, plataforma, titulo, preco, url_afiliado, imagem, postada_em"
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


def registrar_msg_telegram(source_id: str | int, message_id: int, uid: str = "", status: str = "ok") -> None:
    agora = dt.datetime.now().isoformat(timespec="seconds")
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO mensagens_telegram"
            " (source_id, message_id, processada_em, uid, status)"
            " VALUES (?, ?, ?, ?, ?)",
            (str(source_id), int(message_id), agora, uid, status),
        )
        c.execute(
            "UPDATE fontes_telegram SET ultima_msg_id = MAX(ultima_msg_id, ?), ultimo_processamento = ?"
            " WHERE chat_id = ?",
            (int(message_id), agora, str(source_id)),
        )


def listar_fontes_telegram() -> list[dict]:
    with _conn() as c:
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT * FROM fontes_telegram ORDER BY adicionada_em DESC").fetchall()
        return [dict(r) for r in rows]


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
