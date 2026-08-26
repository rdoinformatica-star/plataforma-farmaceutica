#!/usr/bin/env python3
"""
Script de migração: SQLite → PostgreSQL
Usa batch insert para copiar ~572 MB em minutos, não horas.
"""
import sqlite3
import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values
import os
import pathlib
import sys
import time

def get_postgres_url():
    """Lê a URL de conexão PostgreSQL do Railway"""
    url = os.environ.get('DATABASE_URL')
    if not url:
        print("[ERRO] DATABASE_URL não configurada")
        sys.exit(1)
    return url

def sqlite_type_to_postgres(sqlite_type):
    """Converte tipos SQLite para PostgreSQL"""
    if not sqlite_type:
        return "TEXT"

    sqlite_type = sqlite_type.upper()
    if 'INT' in sqlite_type:
        return "INTEGER"
    elif 'REAL' in sqlite_type or 'FLOAT' in sqlite_type:
        return "REAL"
    elif 'BLOB' in sqlite_type:
        return "BYTEA"
    else:
        return "TEXT"

def create_tables_postgres(pg_conn):
    """Cria as tabelas aplicando database/schema_postgres.sql — a MESMA fonte
    que o app usa no startup (db.migrar()). Manter uma copia do schema aqui
    dentro faria as duas divergirem com o tempo."""
    print("  Criando tabelas no PostgreSQL...")
    pg_cursor = pg_conn.cursor()

    schema_path = pathlib.Path(__file__).parent / "database" / "schema_postgres.sql"
    if not schema_path.exists():
        print(f"    ✗ Schema nao encontrado: {schema_path}")
        sys.exit(1)

    try:
        pg_cursor.execute(schema_path.read_text(encoding="utf-8"))
        pg_conn.commit()
        print("    ✓ Todas as tabelas criadas com sucesso!")
    except psycopg2.Error as e:
        print(f"    ⚠ Erro ao criar tabelas: {e}")
        pg_conn.rollback()

def migrate():
    start_time = time.time()

    # Conecta ao SQLite local
    print("[1/4] Conectando ao SQLite local...")
    try:
        sqlite_conn = sqlite3.connect('database/pharma.db', timeout=30)
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cursor = sqlite_conn.cursor()
        print("  ✓ SQLite conectado")
    except Exception as e:
        print(f"  ✗ Erro: {e}")
        sys.exit(1)

    # Conecta ao PostgreSQL com timeout maior
    print("[2/4] Conectando ao PostgreSQL (Railway)...")
    try:
        db_url = get_postgres_url()
        pg_conn = psycopg2.connect(db_url, sslmode='require', connect_timeout=15)
        pg_cursor = pg_conn.cursor()
        print("  ✓ PostgreSQL conectado")
    except Exception as e:
        print(f"  ✗ Erro: {e}")
        sys.exit(1)

    # Cria as tabelas
    print("[3/4] Criando tabelas...")
    try:
        create_tables_postgres(pg_conn)
    except Exception as e:
        print(f"  ⚠ Aviso ao criar tabelas: {e}")

    # Copia dados em batches
    print("[3/4] Copiando dados em batches...")
    try:
        sqlite_cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        existentes = {r[0] for r in sqlite_cursor.fetchall()
                      if not r[0].startswith('sqlite_')}

        # Ordem importa: as chaves estrangeiras do schema exigem que pai venha
        # antes de filho (ex.: imports referencia clients e data_sources, e
        # fact_sales referencia imports). Tabelas fora da lista vao no fim.
        ordem = [
            'schema_version', 'clients', 'data_sources', 'imports',
            'import_columns', 'profiles', 'dim_product', 'dim_pdv',
            'dim_distribuidor', 'source_mappings', 'fact_sales',
            'agg_vendas_mensal', 'fact_inventory', 'fact_market',
            'dossies_html', 'audit_logs', 'price_data', 'analyses',
            'opportunities', 'strategies', 'prompts', 'ai_responses',
        ]
        tables = ([t for t in ordem if t in existentes]
                  + sorted(existentes - set(ordem)))

        total_registros = 0
        falhas = []
        for table in tables:
            # Lê todos os dados da tabela
            sqlite_cursor.execute(f"SELECT * FROM {table}")
            rows = sqlite_cursor.fetchall()

            if not rows:
                print(f"  - {table}: vazio")
                continue

            # Pega nomes das colunas
            cols = [desc[0] for desc in sqlite_cursor.description]
            col_names = ', '.join(cols)

            # Converte para tuples para o execute_values
            values = [tuple(row) for row in rows]

            # Insere em batch (muito mais rápido)
            insert_sql = f"""
                INSERT INTO {table} ({col_names})
                VALUES %s
                ON CONFLICT DO NOTHING
            """
            try:
                execute_values(pg_cursor, insert_sql, values, page_size=1000, fetch=False)
                pg_conn.commit()
                total_registros += len(rows)
                print(f"  ✓ {table}: {len(rows):,} registros")
            except Exception as e:
                # ROLLBACK e essencial: sem ele o Postgres aborta a transacao
                # inteira e TODAS as tabelas seguintes falham em cascata com
                # "current transaction is aborted".
                pg_conn.rollback()
                msg = str(e).strip().splitlines()[0]
                falhas.append((table, msg))
                print(f"  ✗ {table}: {msg}")

        # Reajusta as sequences: as linhas foram inseridas com id explicito,
        # entao o contador de identity continua no valor antigo e o proximo
        # INSERT do app colidiria com um id ja existente.
        print("  Reajustando sequences...")
        for table in tables:
            try:
                pg_cursor.execute(
                    "SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                    "COALESCE((SELECT MAX(id) FROM " + table + "), 1))",
                    (table,),
                )
                pg_conn.commit()
            except Exception:
                pg_conn.rollback()  # tabela sem coluna id/sequence — normal

        elapsed = time.time() - start_time
        print(f"  ✓ Total: {total_registros:,} registros em {elapsed:.1f}s")
        if falhas:
            print(f"\n  ⚠ {len(falhas)} tabela(s) falharam:")
            for t, m in falhas:
                print(f"     - {t}: {m}")

    except Exception as e:
        print(f"  ✗ Erro ao copiar: {e}")
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
