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
    """Cria as tabelas usando o schema.sql convertido para PostgreSQL"""
    print("  Criando tabelas no PostgreSQL...")
    pg_cursor = pg_conn.cursor()

    # Schema PostgreSQL (convertido manualmente de schema.sql)
    pg_schema_sql = """
    CREATE TABLE IF NOT EXISTS schema_version (
      versao      INTEGER PRIMARY KEY,
      aplicado_em TEXT NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS clients (
      id            INTEGER PRIMARY KEY,
      nome          TEXT NOT NULL,
      nome_norm     TEXT NOT NULL,
      cnpj          TEXT,
      uf_principal  TEXT,
      grupo         TEXT,
      ativo         INTEGER NOT NULL DEFAULT 1,
      observacoes   TEXT,
      criado_em     TEXT NOT NULL DEFAULT NOW(),
      atualizado_em TEXT
    );
    CREATE UNIQUE INDEX IF NOT EXISTS ux_clients_nome ON clients(nome_norm);

    CREATE TABLE IF NOT EXISTS data_sources (
      id             INTEGER PRIMARY KEY,
      codigo         TEXT NOT NULL UNIQUE,
      nome           TEXT NOT NULL,
      descricao      TEXT,
      natureza_elo   TEXT NOT NULL,
      granularidade  TEXT,
      unidade_valor  TEXT,
      ativo          INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS imports (
      id                 INTEGER PRIMARY KEY,
      client_id          INTEGER REFERENCES clients(id),
      data_source_id     INTEGER NOT NULL REFERENCES data_sources(id),
      adaptador          TEXT NOT NULL,
      adaptador_conf     REAL,
      adaptador_forcado  INTEGER NOT NULL DEFAULT 0,
      origem             TEXT NOT NULL,
      arquivo_nome       TEXT NOT NULL,
      arquivo_path       TEXT NOT NULL,
      arquivo_bytes      INTEGER NOT NULL,
      sha256             TEXT NOT NULL,
      status             TEXT NOT NULL DEFAULT 'FILA',
      etapa_atual        TEXT,
      progresso          REAL NOT NULL DEFAULT 0,
      linhas_lidas       INTEGER NOT NULL DEFAULT 0,
      linhas_gravadas    INTEGER NOT NULL DEFAULT 0,
      linhas_descartadas INTEGER NOT NULL DEFAULT 0,
      motivo_descarte    TEXT,
      periodo_min        INTEGER,
      periodo_max        INTEGER,
      substituido_por    INTEGER REFERENCES imports(id),
      vigente            INTEGER NOT NULL DEFAULT 1,
      cancelar_pedido    INTEGER NOT NULL DEFAULT 0,
      erro_mensagem      TEXT,
      erro_detalhe       TEXT,
      log_json           TEXT,
      params_json        TEXT,
      duracao_seg        REAL,
      pico_memoria_mb    REAL,
      iniciado_em        TEXT NOT NULL DEFAULT NOW(),
      concluido_em       TEXT
    );
    CREATE INDEX IF NOT EXISTS ix_imports_sha    ON imports(sha256);
    CREATE INDEX IF NOT EXISTS ix_imports_escopo ON imports(client_id, data_source_id, vigente);
    CREATE INDEX IF NOT EXISTS ix_imports_status ON imports(status);

    CREATE TABLE IF NOT EXISTS import_columns (
      id              INTEGER PRIMARY KEY,
      import_id       INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
      ordem           INTEGER NOT NULL,
      nome_original   TEXT NOT NULL,
      nome_norm       TEXT NOT NULL,
      tipo_detectado  TEXT NOT NULL,
      papel_semantico TEXT,
      papel_confianca REAL,
      papel_evidencia TEXT,
      eh_nova         INTEGER NOT NULL DEFAULT 0,
      decisao         TEXT NOT NULL DEFAULT 'PENDENTE',
      decidido_por    TEXT,
      decidido_em     TEXT,
      mapeado_para    TEXT,
      stats_json      TEXT NOT NULL,
      UNIQUE(import_id, nome_original)
    );
    CREATE INDEX IF NOT EXISTS ix_impcols_pend ON import_columns(decisao) WHERE decisao='PENDENTE';

    CREATE TABLE IF NOT EXISTS profiles (
      import_id  INTEGER PRIMARY KEY REFERENCES imports(id) ON DELETE CASCADE,
      gerado_em  TEXT NOT NULL DEFAULT NOW(),
      versao     TEXT NOT NULL DEFAULT '1',
      duracao_ms INTEGER,
      json       TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS dim_product (
      id                 INTEGER PRIMARY KEY,
      chave_natural      TEXT NOT NULL UNIQUE,
      nome_canonico      TEXT NOT NULL,
      ean                TEXT,
      codigo_interno     TEXT,
      apresentacao       TEXT,
      produto_base       TEXT,
      marca              TEXT,
      molecula           TEXT,
      fabricante         TEXT,
      eh_vitamedic       INTEGER NOT NULL DEFAULT 0,
      eh_novo            INTEGER NOT NULL DEFAULT 1,
      primeiro_import_id INTEGER REFERENCES imports(id),
      criado_em          TEXT NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS ix_prod_ean  ON dim_product(ean);
    CREATE INDEX IF NOT EXISTS ix_prod_novo ON dim_product(eh_novo) WHERE eh_novo=1;

    CREATE TABLE IF NOT EXISTS dim_pdv (
      id                 INTEGER PRIMARY KEY,
      chave_natural      TEXT NOT NULL UNIQUE,
      razao_social       TEXT NOT NULL,
      cnpj               TEXT,
      uf                 TEXT,
      cidade             TEXT,
      grupo              TEXT,
      bandeira           TEXT,
      rede               TEXT,
      tipo               TEXT,
      canal              TEXT,
      eh_novo            INTEGER NOT NULL DEFAULT 1,
      primeiro_import_id INTEGER REFERENCES imports(id),
      criado_em          TEXT NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS ix_pdv_uf   ON dim_pdv(uf);
    CREATE INDEX IF NOT EXISTS ix_pdv_novo ON dim_pdv(eh_novo) WHERE eh_novo=1;

    CREATE TABLE IF NOT EXISTS dim_distribuidor (
      id                 INTEGER PRIMARY KEY,
      chave_natural      TEXT NOT NULL UNIQUE,
      nome               TEXT NOT NULL,
      cnpj               TEXT,
      uf                 TEXT,
      client_id          INTEGER REFERENCES clients(id),
      eh_novo            INTEGER NOT NULL DEFAULT 1,
      primeiro_import_id INTEGER REFERENCES imports(id),
      criado_em          TEXT NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS ix_dist_novo ON dim_distribuidor(eh_novo) WHERE eh_novo=1;

    CREATE TABLE IF NOT EXISTS source_mappings (
      id             INTEGER PRIMARY KEY,
      entidade       TEXT NOT NULL,
      data_source_id INTEGER NOT NULL REFERENCES data_sources(id),
      codigo_origem  TEXT,
      texto_origem   TEXT NOT NULL,
      entity_id      INTEGER,
      metodo         TEXT NOT NULL,
      confianca      REAL,
      status         TEXT NOT NULL DEFAULT 'ATIVO',
      confirmado_por TEXT,
      observacao     TEXT,
      criado_em      TEXT NOT NULL DEFAULT NOW(),
      UNIQUE(entidade, data_source_id, texto_origem)
    );
    CREATE INDEX IF NOT EXISTS ix_map_pend ON source_mappings(status) WHERE status='PENDENTE';

    CREATE TABLE IF NOT EXISTS fact_sales (
      id              INTEGER PRIMARY KEY,
      import_id       INTEGER NOT NULL,
      distribuidor_id INTEGER NOT NULL,
      produto_id      INTEGER NOT NULL,
      pdv_id          INTEGER,
      periodo         INTEGER NOT NULL,
      unidades_x100   INTEGER NOT NULL,
      valor_x100      INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS agg_vendas_mensal (
      import_id       INTEGER NOT NULL,
      distribuidor_id INTEGER NOT NULL,
      produto_id      INTEGER NOT NULL,
      uf              TEXT,
      periodo         INTEGER NOT NULL,
      unidades_x100   INTEGER NOT NULL,
      valor_x100      INTEGER NOT NULL,
      n_pdvs          INTEGER NOT NULL,
      PRIMARY KEY (import_id, distribuidor_id, produto_id, uf, periodo)
    );
    CREATE INDEX IF NOT EXISTS ix_agg_periodo ON agg_vendas_mensal(periodo, uf);
    CREATE INDEX IF NOT EXISTS ix_agg_produto ON agg_vendas_mensal(produto_id, periodo);

    CREATE TABLE IF NOT EXISTS fact_inventory (
      id                   INTEGER PRIMARY KEY,
      import_id            INTEGER NOT NULL,
      client_id            INTEGER REFERENCES clients(id),
      filial               TEXT,
      produto_id           INTEGER NOT NULL,
      data_ref             TEXT NOT NULL,
      custo_rep_x100       INTEGER,
      estoque_total_un     REAL,
      estoque_disp_un      REAL,
      estoque_disp_x100    INTEGER,
      cobertura_dias       REAL,
      pendencia_un         REAL,
      transferencia_un     REAL,
      media_venda_x100     INTEGER,
      media_venda_un       REAL,
      media_venda_sgc_x100 INTEGER,
      media_venda_sgc_un   REAL,
      extras_json          TEXT
    );
    CREATE INDEX IF NOT EXISTS ix_inv_prod ON fact_inventory(produto_id, data_ref);
    CREATE INDEX IF NOT EXISTS ix_inv_imp  ON fact_inventory(import_id);

    CREATE TABLE IF NOT EXISTS fact_market (
      id                 INTEGER PRIMARY KEY,
      import_id          INTEGER NOT NULL,
      aba                TEXT NOT NULL,
      periodo_ref        INTEGER,
      mercado            TEXT,
      apresentacao       TEXT,
      molecula           TEXT,
      uf                 TEXT,
      canal              TEXT,
      tipo               TEXT,
      lab_full           TEXT,
      lab_grupo          TEXT,
      eh_vitamedic       INTEGER NOT NULL DEFAULT 0,
      produto_id         INTEGER,
      un_atual           REAL,
      valor_atual_x100   INTEGER,
      un_ant             REAL,
      valor_ant_x100     INTEGER,
      un_ytd             REAL,
      valor_ytd_x100     INTEGER,
      un_ytd_ant         REAL,
      valor_ytd_ant_x100 INTEGER
    );
    CREATE INDEX IF NOT EXISTS ix_mkt_apre ON fact_market(apresentacao, uf);
    CREATE INDEX IF NOT EXISTS ix_mkt_imp  ON fact_market(import_id);

    CREATE TABLE IF NOT EXISTS dossies_html (
      id              INTEGER PRIMARY KEY,
      import_id       INTEGER NOT NULL REFERENCES imports(id),
      distribuidor_id INTEGER REFERENCES dim_distribuidor(id),
      distribuidor_nome_detectado TEXT,
      arquivo_nome    TEXT NOT NULL,
      tabela_indice   INTEGER NOT NULL,
      tabela_titulo   TEXT,
      cabecalhos_json TEXT NOT NULL,
      linhas_json     TEXT NOT NULL,
      criado_em       TEXT NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS ix_dossies_import ON dossies_html(import_id);
    CREATE INDEX IF NOT EXISTS ix_dossies_dist ON dossies_html(distribuidor_id);

    CREATE TABLE IF NOT EXISTS audit_logs (
      id           INTEGER PRIMARY KEY,
      ts           TEXT NOT NULL DEFAULT NOW(),
      ator         TEXT NOT NULL DEFAULT 'usuario',
      acao         TEXT NOT NULL,
      entidade     TEXT,
      entidade_id  INTEGER,
      resumo       TEXT NOT NULL,
      detalhe_json TEXT
    );
    CREATE INDEX IF NOT EXISTS ix_audit_ts ON audit_logs(ts DESC);

    CREATE TABLE IF NOT EXISTS price_data (
      id INTEGER PRIMARY KEY, import_id INTEGER,
      produto_id INTEGER, distribuidor_id INTEGER, uf TEXT, periodo INTEGER,
      elo TEXT NOT NULL,
      preco_x100 INTEGER, origem TEXT
    );

    CREATE TABLE IF NOT EXISTS analyses (
      id INTEGER PRIMARY KEY, client_id INTEGER,
      tipo TEXT NOT NULL, titulo TEXT,
      parametros_json TEXT, resultado_json TEXT,
      calculo_json TEXT,
      rotulo TEXT,
      criado_em TEXT NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS opportunities (
      id INTEGER PRIMARY KEY, client_id INTEGER, analysis_id INTEGER,
      titulo TEXT, impacto_x100 INTEGER, esforco TEXT, prioridade TEXT,
      status TEXT NOT NULL DEFAULT 'ABERTA', evidencia_json TEXT,
      criado_em TEXT NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS strategies (
      id INTEGER PRIMARY KEY, client_id INTEGER, opportunity_id INTEGER,
      titulo TEXT, acao TEXT, responsavel TEXT, prazo TEXT, kpi TEXT,
      status TEXT NOT NULL DEFAULT 'PLANEJADA'
    );

    CREATE TABLE IF NOT EXISTS prompts (
      id INTEGER PRIMARY KEY, client_id INTEGER,
      gatilho TEXT, contexto_json TEXT, texto TEXT NOT NULL,
      criado_em TEXT NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS ai_responses (
      id INTEGER PRIMARY KEY, prompt_id INTEGER REFERENCES prompts(id),
      provedor TEXT NOT NULL DEFAULT 'MANUAL', texto TEXT NOT NULL,
      colado_em TEXT NOT NULL DEFAULT NOW(),
      avaliacao INTEGER
    );
    """

    try:
        pg_cursor.execute(pg_schema_sql)
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
        tables = [row[0] for row in sqlite_cursor.fetchall()]

        total_registros = 0
        for table in tables:
            if table.startswith('sqlite_'):
                continue

            # Lê todos os dados da tabela
            sqlite_cursor.execute(f"SELECT * FROM {table}")
            rows = sqlite_cursor.fetchall()

            if not rows:
                print(f"  - {table}: vazio")
                continue

            # Pega nomes das colunas
            cols = [desc[0] for desc in sqlite_cursor.description]
            col_names = ', '.join(cols)
            placeholders = ', '.join(['%s'] * len(cols))

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
                # Ignora erros de constraints/tipos
                print(f"  ⚠ {table}: {e}")

        elapsed = time.time() - start_time
        print(f"  ✓ Total: {total_registros:,} registros em {elapsed:.1f}s")

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
