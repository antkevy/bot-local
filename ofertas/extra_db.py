"""Tabelas dos recursos extras (espelhamento, disparos, proteção, etc.).

Por que um módulo separado
--------------------------
`ofertas/db.py` é o banco de produção do pipeline e não pode ser alterado: o
histórico de postagens, as fontes e as reservas têm contratos e testes próprios.
Os recursos portados do ScanHub são opt-in e vivem em tabelas NOVAS, criadas
aqui, sem tocar em nenhuma tabela existente.

O caminho é lido de `db.DB_PATH` a cada conexão (e não copiado no import). É o
mesmo cuidado que `db.py` documenta: as suítes redirecionam `db.DB_PATH` para um
arquivo temporário, e um caminho congelado no import faria os testes novos
escreverem no banco do usuário.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from . import db as _db

_SCHEMA = (
    # Espelhamento: canais/grupos para onde cada oferta pode ser replicada.
    # `ativo` é o interruptor por destino — desligar um não mexe nos outros.
    """CREATE TABLE IF NOT EXISTS mirrors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT NOT NULL UNIQUE,
        nome TEXT NOT NULL DEFAULT '',
        ativo INTEGER NOT NULL DEFAULT 1,
        criado_em TEXT NOT NULL
    )""",
    # Disparos unificados: mensagem ou enquete, com ritmo próprio e horário
    # de silêncio. `destinos`, `opcoes` são JSON (lista).
    """CREATE TABLE IF NOT EXISTS broadcasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL DEFAULT 'message',
        texto TEXT NOT NULL,
        imagem TEXT,
        destinos TEXT NOT NULL DEFAULT '[]',
        agendado_para TEXT,
        ritmo_segundos INTEGER NOT NULL DEFAULT 3,
        pergunta TEXT,
        opcoes TEXT NOT NULL DEFAULT '[]',
        multipla INTEGER NOT NULL DEFAULT 0,
        fecha_em TEXT,
        status TEXT NOT NULL DEFAULT 'pendente',
        criado_em TEXT NOT NULL,
        enviado_em TEXT,
        erro TEXT
    )""",
    # Marca d'água: linha única (id=1). Preset define o posicionamento e o
    # handle é o @ digitado no painel.
    """CREATE TABLE IF NOT EXISTS marca_dagua (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        preset TEXT NOT NULL DEFAULT 'final',
        handle TEXT NOT NULL DEFAULT '',
        ativo INTEGER NOT NULL DEFAULT 0
    )""",
    # Credenciais são write-only na API: entram, nunca saem. A coluna existe
    # para uso interno dos módulos que precisam autenticar.
    """CREATE TABLE IF NOT EXISTS credenciais (
        plataforma TEXT PRIMARY KEY,
        segredo TEXT NOT NULL,
        atualizado_em TEXT NOT NULL
    )""",
    # Smart links: slug curto -> URL de afiliado, com contador de cliques.
    """CREATE TABLE IF NOT EXISTS smart_links (
        slug TEXT PRIMARY KEY,
        url TEXT NOT NULL,
        plataforma TEXT NOT NULL DEFAULT '',
        cliques INTEGER NOT NULL DEFAULT 0,
        criado_em TEXT NOT NULL
    )""",
    # Proteção: cada varredura é revisável antes de remover qualquer fonte.
    """CREATE TABLE IF NOT EXISTS protection_scans (
        id TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'revisao',
        criado_em TEXT NOT NULL,
        confirmado_em TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS protection_alvos (
        scan_id TEXT NOT NULL,
        chave TEXT NOT NULL,
        chat_id TEXT NOT NULL,
        nome TEXT NOT NULL DEFAULT '',
        motivo TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pendente',
        PRIMARY KEY (scan_id, chave)
    )""",
)


@contextmanager
def conn():
    """Conexão com as tabelas extras criadas; fecha de verdade no fim.

    Não usa WAL pelo mesmo motivo de `db.py`: criaria `.db-wal`/`.db-shm` no
    diretório de dados do usuário.
    """
    c = sqlite3.connect(_db.DB_PATH)
    try:
        for ddl in _SCHEMA:
            c.execute(ddl)
        c.execute("PRAGMA busy_timeout=5000")
        c.commit()
        yield c
        c.commit()
    except BaseException:
        c.rollback()
        raise
    finally:
        c.close()


def init_db() -> None:
    """Garante as tabelas extras sem depender do pipeline."""
    with conn():
        pass
