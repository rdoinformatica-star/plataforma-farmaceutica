"""
Camada de BD híbrida: SQLite (local) ou PostgreSQL (production)
Detecta automaticamente baseado em DATABASE_URL
"""
import os
import sqlite3
from contextlib import contextmanager

# Se DATABASE_URL está definida, usa PostgreSQL; senão usa SQLite
USE_POSTGRES = bool(os.environ.get('DATABASE_URL'))

if USE_POSTGRES:
    try:
        import psycopg2
        from psycopg2 import sql
    except ImportError:
        raise ImportError("psycopg2 necessário para usar PostgreSQL. Instale com: pip install psycopg2-binary")

from . import settings

@contextmanager
def conectar():
    """Abre uma conexão (SQLite ou PostgreSQL)"""
    if USE_POSTGRES:
        db_url = os.environ.get('DATABASE_URL')
        conn = psycopg2.connect(db_url, sslmode='require')
        conn.autocommit = True

        # Wrapper pra compatibilidade com SQLite
        class PgWrapper:
            def __init__(self, real_conn):
                self.real_conn = real_conn
                self.cursor_obj = None

            def cursor(self):
                return self.real_conn.cursor()

            def execute(self, query, *args):
                cur = self.real_conn.cursor()
                cur.execute(query, args if args else ())
                return cur

            def close(self):
                self.real_conn.close()

        conn_wrapper = PgWrapper(conn)
        try:
            yield conn_wrapper
        finally:
            conn.close()
    else:
        # SQLite local (comportamento original)
        conn = sqlite3.connect(settings.DB_PATH, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row

        # PRAGMAS pra otimizar
        pragmas = (
            "PRAGMA journal_mode = WAL",
            "PRAGMA synchronous = NORMAL",
            "PRAGMA foreign_keys = ON",
            "PRAGMA busy_timeout = 15000",
            "PRAGMA cache_size = -32768",
        )
        for p in pragmas:
            conn.execute(p)

        try:
            yield conn
        finally:
            conn.close()

print(f"[DB] Usando: {'PostgreSQL' if USE_POSTGRES else 'SQLite local'}")
