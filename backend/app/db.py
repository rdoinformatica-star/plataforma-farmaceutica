"""Acesso a dados: SQLite (dev local) ou PostgreSQL (producao), pela
variavel DATABASE_URL.

O caminho critico e um executemany de milhoes de linhas com PRAGMAs proprios
(SQLite) / execute_values (Postgres); uma camada de ORM em cima disso so
atrapalharia.

Design: as ~30 chamadoras deste modulo (routers, analytics/, ingest/) usam
`con.execute(sql, params)` com placeholders `?` e tratam o retorno como
sqlite3.Row (acesso por nome, por indice, e desempacotamento posicional
`for k, v in con.execute(...)`). Em vez de reescrever cada uma delas para
dois dialetos, `conectar()` devolve, sob Postgres, um wrapper "duck-typed"
que aceita a mesma sintaxe SQLite (`?`, `datetime('now','localtime')`,
PRAGMA-como-no-op) e devolve linhas com a mesma interface do sqlite3.Row.
Isso mantem 100% do codigo chamador inalterado nos dois modos.
"""
import os
import re
import sqlite3
from contextlib import contextmanager

from . import settings

USE_POSTGRES = bool(os.environ.get("DATABASE_URL"))

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool

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


def _abrir_sqlite(pragmas) -> sqlite3.Connection:
    con = sqlite3.connect(settings.DB_PATH, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    for p in pragmas:
        con.execute(p)
    return con


# ══════════════════════════ camada Postgres (adapter) ═══════════════════

if USE_POSTGRES:
    _PG_POOL = None

    # Casa aspas simples (preservando '' escapado dentro) OU um '?' solto.
    # So o '?' fora de literal e trocado por '%s' — protege LIKE/JSON que
    # por acaso tenham um '?' dentro de uma string.
    _PLACEHOLDER_RE = re.compile(r"'(?:[^']|'')*'|(\?)")

    def _traduzir_sql(sql: str) -> str:
        sql = sql.replace("datetime('now','localtime')", "NOW()")

        def _sub(m):
            return "%s" if m.group(1) else m.group(0)

        return _PLACEHOLDER_RE.sub(_sub, sql)

    def _pg_pool():
        global _PG_POOL
        if _PG_POOL is None:
            _PG_POOL = psycopg2.pool.ThreadedConnectionPool(
                1, 10, dsn=os.environ["DATABASE_URL"]
            )
        return _PG_POOL

    def _pg_getconn():
        pool = _pg_pool()
        raw = pool.getconn()
        raw.autocommit = True
        try:
            with raw.cursor() as c:
                c.execute("SELECT 1")
        except psycopg2.Error:
            # conexao ficou obsoleta (comum em Postgres serverless, ex. Neon,
            # que derruba conexoes ociosas) — descarta e pega outra do pool.
            pool.putconn(raw, close=True)
            raw = pool.getconn()
            raw.autocommit = True
        return raw

    class _Row:
        """Imita sqlite3.Row: acesso por nome, por indice, iteravel por
        valores (nao por chaves) e compativel com dict(row)."""

        __slots__ = ("_values", "_index")

        def __init__(self, values, index):
            self._values = values
            self._index = index

        def __getitem__(self, key):
            if isinstance(key, str):
                return self._values[self._index[key]]
            return self._values[key]

        def __iter__(self):
            return iter(self._values)

        def __len__(self):
            return len(self._values)

        def keys(self):
            return self._index.keys()

        def __repr__(self):
            return repr(dict(zip(self._index.keys(), self._values)))

    class _NoOpCursor:
        """Devolvido para PRAGMA sob Postgres — nao existe equivalente."""

        def fetchone(self):
            return None

        def fetchall(self):
            return []

        def __iter__(self):
            return iter(())

        lastrowid = None
        rowcount = -1

    class _PgCursor:
        def __init__(self, cur):
            self._cur = cur
            self._index = (
                {d.name: i for i, d in enumerate(cur.description)}
                if cur.description
                else None
            )

        def _wrap(self, row):
            return None if row is None else _Row(row, self._index)

        def fetchone(self):
            if self._index is None:
                return None
            return self._wrap(self._cur.fetchone())

        def fetchall(self):
            if self._index is None:
                return []
            return [self._wrap(r) for r in self._cur.fetchall()]

        def __iter__(self):
            if self._index is None:
                return iter(())
            return (self._wrap(r) for r in self._cur)

        @property
        def lastrowid(self):
            with self._cur.connection.cursor() as c2:
                c2.execute("SELECT LASTVAL()")
                return c2.fetchone()[0]

        @property
        def rowcount(self):
            return self._cur.rowcount

    class _PgConnection:
        def __init__(self, raw):
            self._raw = raw

        def execute(self, sql, params=()):
            if sql.strip()[:6].upper() == "PRAGMA":
                return _NoOpCursor()
            sql2 = _traduzir_sql(sql)
            cur = self._raw.cursor()
            cur.execute(sql2, params if params else None)
            return _PgCursor(cur)

        def executemany(self, sql, seq_params):
            sql2 = _traduzir_sql(sql)
            m = re.search(r"VALUES\s*\(\s*(?:%s\s*,?\s*)+\)", sql2, re.IGNORECASE)
            cur = self._raw.cursor()
            if m:
                # Reescreve "VALUES (%s, %s, ...)" -> "VALUES %s" para o
                # execute_values fazer um INSERT multi-linha por rede em vez
                # de um round-trip por linha (essencial para os ~6,8M
                # registros de fact_sales).
                template_sql = sql2[: m.start()] + "VALUES %s" + sql2[m.end() :]
                psycopg2.extras.execute_values(
                    cur, template_sql, seq_params, page_size=1000
                )
            else:
                cur.executemany(sql2, seq_params)
            return _PgCursor(cur)

        def cursor(self):
            return _PgCursor(self._raw.cursor())

        def commit(self):
            pass  # autocommit=True; BEGIN/COMMIT explicitos (ver transacao()) ja funcionam via SQL puro

        def close(self):
            _pg_pool().putconn(self._raw)


# ═══════════════════════════════ API publica ═════════════════════════════


def conectar():
    if USE_POSTGRES:
        return _PgConnection(_pg_getconn())
    return _abrir_sqlite(_PRAGMAS_API)


def conectar_carga():
    if USE_POSTGRES:
        return _PgConnection(_pg_getconn())
    return _abrir_sqlite(_PRAGMAS_CARGA)


def encerrar_carga(con) -> None:
    if USE_POSTGRES:
        return  # sem PRAGMAs equivalentes; nada a fazer
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
    """Aplica o schema (SQLite ou Postgres, conforme DATABASE_URL). Idempotente
    — pode rodar a cada subida."""
    con = conectar()
    try:
        if USE_POSTGRES:
            schema = settings.SCHEMA_POSTGRES_SQL.read_text(encoding="utf-8")
            seed = settings.SEED_POSTGRES_SQL.read_text(encoding="utf-8")
            con.execute(schema)
            con.execute(seed)
            con.execute(
                "INSERT INTO schema_version(versao) VALUES (?) "
                "ON CONFLICT DO NOTHING",
                (1,),
            )
            tabelas = [
                r["name"]
                for r in con.execute(
                    "SELECT table_name AS name FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_type='BASE TABLE' "
                    "ORDER BY table_name"
                )
            ]
        else:
            schema = settings.SCHEMA_SQL.read_text(encoding="utf-8")
            seed = settings.SEED_SQL.read_text(encoding="utf-8")
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


def uma(con, sql: str, params=()) -> dict | None:
    row = con.execute(sql, params).fetchone()
    return dict(row) if row else None


def varias(con, sql: str, params=()) -> list[dict]:
    return [dict(r) for r in con.execute(sql, params)]


def escalar(con, sql: str, params=()):
    row = con.execute(sql, params).fetchone()
    return row[0] if row else None
