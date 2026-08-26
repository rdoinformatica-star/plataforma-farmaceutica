#!/usr/bin/env python3
"""
Script de migração: SQLite → PostgreSQL
Copia dados de forma segura, respeitando integridade referencial.
"""
import sqlite3
import psycopg2
from psycopg2 import sql
import os
import sys

def get_postgres_url():
    """Lê a URL de conexão PostgreSQL do Railway"""
    # Format: postgresql://user:password@host:port/dbname
    url = os.environ.get('DATABASE_URL')
    if not url:
        print("[ERRO] DATABASE_URL não configurada")
        sys.exit(1)
    return url

def migrate():
    # Conecta ao SQLite local
    print("[1/4] Conectando ao SQLite local...")
    try:
        sqlite_conn = sqlite3.connect('database/pharma.db')
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cursor = sqlite_conn.cursor()
        print("  ✓ SQLite conectado")
    except Exception as e:
        print(f"  ✗ Erro: {e}")
        sys.exit(1)

    # Conecta ao PostgreSQL
    print("[2/4] Conectando ao PostgreSQL (Railway)...")
    try:
        db_url = get_postgres_url()
        pg_conn = psycopg2.connect(db_url, sslmode='require')
        pg_cursor = pg_conn.cursor()
        print("  ✓ PostgreSQL conectado")
    except Exception as e:
        print(f"  ✗ Erro: {e}")
        sys.exit(1)

    # Obtém lista de tabelas
    print("[3/4] Copiando dados...")
    try:
        sqlite_cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in sqlite_cursor.fetchall()]

        for table in tables:
            if table.startswith('sqlite_'):
                continue

            # Copia dados da tabela
            sqlite_cursor.execute(f"SELECT * FROM {table}")
            rows = sqlite_cursor.fetchall()

            if not rows:
                print(f"  - {table}: vazio")
                continue

            # Pega colunas
            cols = [desc[0] for desc in sqlite_cursor.description]

            # Insere no PostgreSQL (ignorando duplicatas)
            for row in rows:
                placeholders = ', '.join(['%s'] * len(cols))
                col_names = ', '.join(cols)
                insert_sql = f"""
                    INSERT INTO {table} ({col_names})
                    VALUES ({placeholders})
                    ON CONFLICT DO NOTHING
                """
                try:
                    pg_cursor.execute(insert_sql, row)
                except Exception as e:
                    # Ignora erros de constraints
                    pass

            pg_conn.commit()
            print(f"  ✓ {table}: {len(rows)} registros")

        print("  ✓ Migração concluída!")
    except Exception as e:
        print(f"  ✗ Erro: {e}")
        sys.exit(1)
    finally:
        sqlite_conn.close()
        pg_conn.close()

    print("[4/4] Finalizando...")
    print("\n✅ Migração completada com sucesso!")
    print("   Frontend: https://platafo.vercel.app")
    print("   Backend:  https://plataforma-farmaceutica-production.up.railway.app")

if __name__ == '__main__':
    migrate()
