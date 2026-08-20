"""Acesso ao SQLite. sqlite3 puro, sem ORM.

O caminho critico e um executemany de milhoes de linhas com PRAGMAs proprios;
uma camada de ORM em cima disso so atrapalharia.
"""
import sqlite3
from contextlib import contextmanager

from . import settings

_PRAGMAS_API = (
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA foreign_keys = ON",
    "PRAGMA busy_timeout = 15000",
    "PRAGMA cache_size = -32768",
)

# Usados so durante a carga em massa, numa conexao dedicada.
_PRAGMAS_CARGA = (
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = OFF",
    "PRAGMA foreign_keys = OFF",
    "PRAGMA busy_timeout = 60000",
    "PRAGMA cache_size = -262144",
    "PRAGMA temp_store = MEMORY",
    "PRAGMA wal_autocheckpoint = 4000",
)


def _abrir(pragmas) -> sqlite3.Connection:
    con = sqlite3.connect(settings.DB_PATH, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    for p in pragmas:
        con.execute(p)
    return con


def conectar() -> sqlite3.Connection:
    return _abrir(_PRAGMAS_API)


def conectar_carga() -> sqlite3.Connection:
    return _abrir(_PRAGMAS_CARGA)


def encerrar_carga(con: sqlite3.Connection) -> None:
    con.execute("PRAGMA synchronous = NORMAL")
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    con.execute("PRAGMA optimize")


@contextmanager
def conexao():
    con = conectar()
    try:
        yield con
    finally:
        con.close()


@contextmanager
def transacao():
    con = conectar()
    try:
        con.execute("BEGIN")
        yield con
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def migrar() -> dict:
    """Aplica schema.sql e seed.sql. Idempotente — pode rodar a cada subida."""
    schema = settings.SCHEMA_SQL.read_text(encoding="utf-8")
    seed = settings.SEED_SQL.read_text(encoding="utf-8")
    con = conectar()
    try:
        con.executescript(schema)
        con.executescript(seed)
        con.execute(
            "INSERT OR IGNORE INTO schema_version(versao) VALUES (?)", (1,)
        )
        tabelas = [
            r["name"]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        fontes = con.execute("SELECT count(*) AS n FROM data_sources").fetchone()["n"]
        return {"tabelas": tabelas, "fontes": fontes}
    finally:
        con.close()


def uma(con: sqlite3.Connection, sql: str, params=()) -> dict | None:
    row = con.execute(sql, params).fetchone()
    return dict(row) if row else None


def varias(con: sqlite3.Connection, sql: str, params=()) -> list[dict]:
    return [dict(r) for r in con.execute(sql, params)]


def escalar(con: sqlite3.Connection, sql: str, params=()):
    row = con.execute(sql, params).fetchone()
    return row[0] if row else None
