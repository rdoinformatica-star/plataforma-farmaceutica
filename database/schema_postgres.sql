-- PHARMA INTELLIGENCE — esquema do banco (variante PostgreSQL)
--
-- Conversao manual de schema.sql (SQLite) para Postgres:
--   * id INTEGER PRIMARY KEY -> id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY
--     (Postgres nao auto-incrementa INTEGER PRIMARY KEY como o rowid do SQLite)
--   * DEFAULT (datetime('now','localtime')) -> DEFAULT NOW()
--   * sem PRAGMA, sem WITHOUT ROWID (conceitos exclusivos do SQLite)
--   * mesmas convencoes de negocio do schema.sql: dinheiro/unidades em INTEIRO x100,
--     nomes em portugues.

CREATE TABLE IF NOT EXISTS schema_version (
  versao      INTEGER PRIMARY KEY,
  aplicado_em TEXT NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════ CADASTRO ═══════════════════════════════

CREATE TABLE IF NOT EXISTS clients (
  id            INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
  id             INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  codigo         TEXT NOT NULL UNIQUE,
  nome           TEXT NOT NULL,
  descricao      TEXT,
  natureza_elo   TEXT NOT NULL,
  granularidade  TEXT,
  unidade_valor  TEXT,
  ativo          INTEGER NOT NULL DEFAULT 1
);

-- ══════════════════════════════ IMPORTACAO ══════════════════════════════

CREATE TABLE IF NOT EXISTS imports (
  id                 INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
  id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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

-- ═══════════════════════════════ DIMENSOES ══════════════════════════════

CREATE TABLE IF NOT EXISTS dim_product (
  id                 INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
  id                 INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
  id                 INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
  id             INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  entidade       TEXT NOT NULL CHECK (entidade IN ('PRODUTO','PDV','DISTRIBUIDOR')),
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

-- ═════════════════════════════════ FATOS ════════════════════════════════

CREATE TABLE IF NOT EXISTS fact_sales (
  id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
  id                   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
  id                 INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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

-- ════════════════════════════════ AUDITORIA ═════════════════════════════

CREATE TABLE IF NOT EXISTS dossies_html (
  id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
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
  id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ts           TEXT NOT NULL DEFAULT NOW(),
  ator         TEXT NOT NULL DEFAULT 'usuario',
  acao         TEXT NOT NULL,
  entidade     TEXT,
  entidade_id  INTEGER,
  resumo       TEXT NOT NULL,
  detalhe_json TEXT
);
CREATE INDEX IF NOT EXISTS ix_audit_ts ON audit_logs(ts DESC);

-- ═══════════════ TABELAS DAS ETAPAS SEGUINTES (criadas vazias) ══════════

CREATE TABLE IF NOT EXISTS price_data (
  id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY, import_id INTEGER,
  produto_id INTEGER, distribuidor_id INTEGER, uf TEXT, periodo INTEGER,
  elo TEXT NOT NULL,
  preco_x100 INTEGER, origem TEXT
);

CREATE TABLE IF NOT EXISTS analyses (
  id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY, client_id INTEGER,
  tipo TEXT NOT NULL, titulo TEXT,
  parametros_json TEXT, resultado_json TEXT,
  calculo_json TEXT,
  rotulo TEXT,
  criado_em TEXT NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS opportunities (
  id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY, client_id INTEGER, analysis_id INTEGER,
  titulo TEXT, impacto_x100 INTEGER, esforco TEXT, prioridade TEXT,
  status TEXT NOT NULL DEFAULT 'ABERTA', evidencia_json TEXT,
  criado_em TEXT NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategies (
  id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY, client_id INTEGER, opportunity_id INTEGER,
  titulo TEXT, acao TEXT, responsavel TEXT, prazo TEXT, kpi TEXT,
  status TEXT NOT NULL DEFAULT 'PLANEJADA'
);

CREATE TABLE IF NOT EXISTS prompts (
  id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY, client_id INTEGER,
  gatilho TEXT, contexto_json TEXT, texto TEXT NOT NULL,
  criado_em TEXT NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai_responses (
  id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY, prompt_id INTEGER REFERENCES prompts(id),
  provedor TEXT NOT NULL DEFAULT 'MANUAL', texto TEXT NOT NULL,
  colado_em TEXT NOT NULL DEFAULT NOW(),
  avaliacao INTEGER
);

-- ═════════════════════════════════ VIEWS ════════════════════════════════

CREATE OR REPLACE VIEW v_vendas AS
SELECT f.id, f.import_id, f.distribuidor_id, f.produto_id, f.pdv_id, f.periodo,
       f.unidades_x100 / 100.0 AS unidades,
       f.valor_x100    / 100.0 AS valor
  FROM fact_sales f
  JOIN imports i ON i.id = f.import_id
 WHERE i.vigente = 1 AND i.status = 'CONCLUIDO';

CREATE OR REPLACE VIEW v_vendas_mensal AS
SELECT a.distribuidor_id, a.produto_id, a.uf, a.periodo, a.n_pdvs,
       a.unidades_x100 / 100.0 AS unidades,
       a.valor_x100    / 100.0 AS valor
  FROM agg_vendas_mensal a
  JOIN imports i ON i.id = a.import_id
 WHERE i.vigente = 1 AND i.status = 'CONCLUIDO';

CREATE OR REPLACE VIEW v_estoque AS
SELECT e.*,
       e.estoque_disp_x100 / 100.0 AS estoque_disp_valor,
       e.media_venda_x100  / 100.0 AS media_venda_valor,
       e.custo_rep_x100    / 100.0 AS custo_reposicao
  FROM fact_inventory e
  JOIN imports i ON i.id = e.import_id
 WHERE i.vigente = 1 AND i.status = 'CONCLUIDO';

CREATE OR REPLACE VIEW v_mercado AS
SELECT m.*,
       m.valor_atual_x100   / 100.0 AS valor_atual,
       m.valor_ant_x100     / 100.0 AS valor_ant,
       m.valor_ytd_x100     / 100.0 AS valor_ytd,
       m.valor_ytd_ant_x100 / 100.0 AS valor_ytd_ant
  FROM fact_market m
  JOIN imports i ON i.id = m.import_id
 WHERE i.vigente = 1 AND i.status = 'CONCLUIDO';
