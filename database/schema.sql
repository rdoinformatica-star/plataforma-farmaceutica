-- PHARMA INTELLIGENCE — esquema do banco
--
-- Convencoes:
--   * dinheiro e unidades em INTEIRO x100 (o sufixo _x100 esta no nome da coluna).
--     Casa com ESCALA = 100.0 do formato VMD1 e torna a soma exata.
--     A divisao por 100 acontece num lugar so: as views v_*.
--   * timestamps em TEXT ISO (datetime('now','localtime')).
--   * nomes de negocio em portugues, porque o usuario le o banco.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
  versao      INTEGER PRIMARY KEY,
  aplicado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ═══════════════════════════════ CADASTRO ═══════════════════════════════

CREATE TABLE IF NOT EXISTS clients (
  id            INTEGER PRIMARY KEY,
  nome          TEXT NOT NULL,
  nome_norm     TEXT NOT NULL,          -- maiusculo sem acento, para busca e unicidade
  cnpj          TEXT,
  uf_principal  TEXT,
  grupo         TEXT,
  ativo         INTEGER NOT NULL DEFAULT 1,
  observacoes   TEXT,
  criado_em     TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  atualizado_em TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_clients_nome ON clients(nome_norm);

-- natureza_elo e o guarda-corpo contra o erro mais caro do dominio:
-- comparar preco IQVIA (PDV -> consumidor) com preco de sell-out
-- (distribuidor -> PDV). Sao elos diferentes da cadeia e nao se comparam.
CREATE TABLE IF NOT EXISTS data_sources (
  id             INTEGER PRIMARY KEY,
  codigo         TEXT NOT NULL UNIQUE,  -- SELLOUT|IQVIA|ESTOQUE|CADASTRO|PDVS|PRECOS|OUTROS
  nome           TEXT NOT NULL,
  descricao      TEXT,
  natureza_elo   TEXT NOT NULL,         -- INDUSTRIA_DISTRIBUIDOR|DISTRIBUIDOR_PDV|
                                        -- PDV_CONSUMIDOR|ESTOQUE|CADASTRAL|INDEFINIDO
  granularidade  TEXT,
  unidade_valor  TEXT,
  ativo          INTEGER NOT NULL DEFAULT 1
);

-- ══════════════════════════════ IMPORTACAO ══════════════════════════════

CREATE TABLE IF NOT EXISTS imports (
  id                 INTEGER PRIMARY KEY,
  client_id          INTEGER REFERENCES clients(id),
  data_source_id     INTEGER NOT NULL REFERENCES data_sources(id),
  adaptador          TEXT NOT NULL,
  adaptador_conf     REAL,
  adaptador_forcado  INTEGER NOT NULL DEFAULT 0,
  origem             TEXT NOT NULL,     -- UPLOAD | DISCO
  arquivo_nome       TEXT NOT NULL,
  arquivo_path       TEXT NOT NULL,
  arquivo_bytes      INTEGER NOT NULL,
  sha256             TEXT NOT NULL,
  status             TEXT NOT NULL DEFAULT 'FILA',
                     -- FILA|ABRINDO|PERFILANDO|DIMENSOES|CARREGANDO|INDEXANDO|
                     -- CONCLUIDO|ERRO|CANCELADO
  etapa_atual        TEXT,
  progresso          REAL NOT NULL DEFAULT 0,
  linhas_lidas       INTEGER NOT NULL DEFAULT 0,
  linhas_gravadas    INTEGER NOT NULL DEFAULT 0,
  linhas_descartadas INTEGER NOT NULL DEFAULT 0,
  motivo_descarte    TEXT,
  periodo_min        INTEGER,
  periodo_max        INTEGER,
  substituido_por    INTEGER REFERENCES imports(id),
  vigente            INTEGER NOT NULL DEFAULT 1,   -- 1 = entra nos calculos
  cancelar_pedido    INTEGER NOT NULL DEFAULT 0,   -- flag cooperativa de cancelamento
  erro_mensagem      TEXT,
  erro_detalhe       TEXT,
  log_json           TEXT,
  params_json        TEXT,
  duracao_seg        REAL,
  pico_memoria_mb    REAL,
  iniciado_em        TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  concluido_em       TEXT
);
CREATE INDEX IF NOT EXISTS ix_imports_sha    ON imports(sha256);
CREATE INDEX IF NOT EXISTS ix_imports_escopo ON imports(client_id, data_source_id, vigente);
CREATE INDEX IF NOT EXISTS ix_imports_status ON imports(status);

-- Suporta o fluxo "NOVO CAMPO DETECTADO": nada e descartado em silencio.
CREATE TABLE IF NOT EXISTS import_columns (
  id              INTEGER PRIMARY KEY,
  import_id       INTEGER NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
  ordem           INTEGER NOT NULL,
  nome_original   TEXT NOT NULL,
  nome_norm       TEXT NOT NULL,
  tipo_detectado  TEXT NOT NULL,   -- INTEIRO|DECIMAL|TEXTO|DATA|PERIODO|BOOLEANO|VAZIO
  papel_semantico TEXT,            -- PRODUTO|PDV|UF|CIDADE|PERIODO|VALOR|UNIDADE|
                                   -- CODIGO_EAN|CNPJ|CATEGORIA|CHAVE|DESCONHECIDO
  papel_confianca REAL,
  papel_evidencia TEXT,            -- frase auditavel, mostrada na interface
  eh_nova         INTEGER NOT NULL DEFAULT 0,
  decisao         TEXT NOT NULL DEFAULT 'PENDENTE',
                                   -- PENDENTE|ARMAZENAR|IGNORAR|MAPEAR|RELACIONAR
  decidido_por    TEXT,
  decidido_em     TEXT,
  mapeado_para    TEXT,
  stats_json      TEXT NOT NULL,
  UNIQUE(import_id, nome_original)
);
CREATE INDEX IF NOT EXISTS ix_impcols_pend ON import_columns(decisao) WHERE decisao='PENDENTE';

CREATE TABLE IF NOT EXISTS profiles (
  import_id  INTEGER PRIMARY KEY REFERENCES imports(id) ON DELETE CASCADE,
  gerado_em  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  versao     TEXT NOT NULL DEFAULT '1',
  duracao_ms INTEGER,
  json       TEXT NOT NULL
);

-- ═══════════════════════════════ DIMENSOES ══════════════════════════════
-- chave_natural e sempre TEXTUAL, nunca o indice posicional do arquivo:
-- os indices mudam entre versoes do export e duplicariam tudo na reimportacao.

CREATE TABLE IF NOT EXISTS dim_product (
  id                 INTEGER PRIMARY KEY,
  chave_natural      TEXT NOT NULL UNIQUE,  -- EAN quando houver, senao texto normalizado
  nome_canonico      TEXT NOT NULL,
  ean                TEXT,
  codigo_interno     TEXT,                  -- codigo do fabricante (FCC no sell-out)
  apresentacao       TEXT,
  produto_base       TEXT,
  marca              TEXT,
  molecula           TEXT,                  -- vem do IQVIA
  fabricante         TEXT,
  eh_vitamedic       INTEGER NOT NULL DEFAULT 0,
  eh_novo            INTEGER NOT NULL DEFAULT 1,  -- marcado com o selo "novo" ate revisar
  primeiro_import_id INTEGER REFERENCES imports(id),
  criado_em          TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_prod_ean  ON dim_product(ean);
CREATE INDEX IF NOT EXISTS ix_prod_novo ON dim_product(eh_novo) WHERE eh_novo=1;

CREATE TABLE IF NOT EXISTS dim_pdv (
  id                 INTEGER PRIMARY KEY,
  chave_natural      TEXT NOT NULL UNIQUE,  -- CNPJ se houver; senao razao_norm|uf|cidade
  razao_social       TEXT NOT NULL,
  cnpj               TEXT,
  uf                 TEXT,
  cidade             TEXT,
  -- Tres niveis diferentes de agrupamento do varejo, guardados separados porque
  -- misturar os tres da conclusao errada sobre concentracao de carteira.
  grupo              TEXT,   -- rede de farmacias do PDV. NAO e o distribuidor.
  bandeira           TEXT,
  rede               TEXT,
  tipo               TEXT,
  canal              TEXT,
  eh_novo            INTEGER NOT NULL DEFAULT 1,
  primeiro_import_id INTEGER REFERENCES imports(id),
  criado_em          TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_pdv_uf   ON dim_pdv(uf);
CREATE INDEX IF NOT EXISTS ix_pdv_novo ON dim_pdv(eh_novo) WHERE eh_novo=1;

-- ATENCAO: distribuidor = quem VENDE para o PDV (o cliente do gerente de contas,
-- campo provNome do VMD1). NAO confundir com dim_pdv.grupo, que e a REDE do PDV.
-- Trocar os dois destroi toda analise de carteira, churn e cobertura.
CREATE TABLE IF NOT EXISTS dim_distribuidor (
  id                 INTEGER PRIMARY KEY,
  chave_natural      TEXT NOT NULL UNIQUE,  -- CNPJ quando houver, senao nome_norm
  nome               TEXT NOT NULL,
  cnpj               TEXT,
  uf                 TEXT,
  client_id          INTEGER REFERENCES clients(id),
  eh_novo            INTEGER NOT NULL DEFAULT 1,
  primeiro_import_id INTEGER REFERENCES imports(id),
  criado_em          TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS ix_dist_novo ON dim_distribuidor(eh_novo) WHERE eh_novo=1;

-- Ponte entre identificadores de fontes diferentes ("MAPEAMENTO DE FONTES").
CREATE TABLE IF NOT EXISTS source_mappings (
  id             INTEGER PRIMARY KEY,
  entidade       TEXT NOT NULL CHECK (entidade IN ('PRODUTO','PDV','DISTRIBUIDOR')),
  data_source_id INTEGER NOT NULL REFERENCES data_sources(id),
  codigo_origem  TEXT,
  texto_origem   TEXT NOT NULL,
  entity_id      INTEGER,               -- id em dim_product/dim_pdv/dim_distribuidor
  metodo         TEXT NOT NULL,         -- EXATO|EAN|NORMALIZADO|FUZZY|MANUAL
  confianca      REAL,
  status         TEXT NOT NULL DEFAULT 'ATIVO',   -- ATIVO|PENDENTE|REJEITADO
  confirmado_por TEXT,
  observacao     TEXT,
  criado_em      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  UNIQUE(entidade, data_source_id, texto_origem)
);
CREATE INDEX IF NOT EXISTS ix_map_pend ON source_mappings(status) WHERE status='PENDENTE';

-- ═════════════════════════════════ FATOS ════════════════════════════════

-- Grao do VMD1: distribuidor x produto x PDV x mes. Guardado BRUTO, nao agregado:
-- agregar aqui destruiria as analises de PDV (churn, white spot, cobertura).
--
-- import_id e FK LOGICA de proposito (sem REFERENCES): com foreign_keys=ON cada
-- INSERT dispararia verificacao de integridade — 6,8 milhoes de lookups.
-- A integridade e garantida no loader (sempre grava o import_id do job corrente)
-- e conferida por um SELECT ao final da carga.
CREATE TABLE IF NOT EXISTS fact_sales (
  id              INTEGER PRIMARY KEY,
  import_id       INTEGER NOT NULL,
  distribuidor_id INTEGER NOT NULL,
  produto_id      INTEGER NOT NULL,
  pdv_id          INTEGER,
  periodo         INTEGER NOT NULL,     -- AAAAMM
  unidades_x100   INTEGER NOT NULL,
  valor_x100      INTEGER NOT NULL
);
-- Os indices de fact_sales NAO ficam aqui: sao criados pelo loader DEPOIS da
-- carga em massa (criar antes multiplica o tempo de insercao). Ver loader.py.

-- Resumo mensal materializado ao fim da carga do sell-out.
-- No arquivo real sao ~373 mil linhas contra 6,8 milhoes: o que faz uma varredura
-- nacional (ranking, totais do pais) cair de segundos para milissegundos.
-- Nao substitui fact_sales: analise por PDV (churn, cobertura, white spot)
-- continua saindo do grao bruto, porque contagem de PDV distinto nao se soma.
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
) WITHOUT ROWID;
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

-- IQVIA. Desnormalizado de proposito: sao dezenas de milhares de linhas, nao
-- milhoes, e as etapas seguintes filtram por texto.
CREATE TABLE IF NOT EXISTS fact_market (
  id                 INTEGER PRIMARY KEY,
  import_id          INTEGER NOT NULL,
  aba                TEXT NOT NULL,     -- m24 | m5
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
  produto_id         INTEGER,           -- via source_mappings, quando houver
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

CREATE TABLE IF NOT EXISTS audit_logs (
  id           INTEGER PRIMARY KEY,
  ts           TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  ator         TEXT NOT NULL DEFAULT 'usuario',
  acao         TEXT NOT NULL,
  entidade     TEXT,
  entidade_id  INTEGER,
  resumo       TEXT NOT NULL,
  detalhe_json TEXT
);
CREATE INDEX IF NOT EXISTS ix_audit_ts ON audit_logs(ts DESC);

-- ═══════════════ TABELAS DAS ETAPAS SEGUINTES (criadas vazias) ══════════
-- Existem desde ja para que o contrato do banco fique estavel.

CREATE TABLE IF NOT EXISTS price_data (
  id INTEGER PRIMARY KEY, import_id INTEGER,
  produto_id INTEGER, distribuidor_id INTEGER, uf TEXT, periodo INTEGER,
  elo TEXT NOT NULL,          -- obrigatorio: de que elo da cadeia e este preco
  preco_x100 INTEGER, origem TEXT
);

CREATE TABLE IF NOT EXISTS analyses (
  id INTEGER PRIMARY KEY, client_id INTEGER,
  tipo TEXT NOT NULL, titulo TEXT,
  parametros_json TEXT, resultado_json TEXT,
  calculo_json TEXT,          -- alimenta o "ver como foi calculado"
  rotulo TEXT,                -- FATO | HIPOTESE | RECOMENDACAO
  criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS opportunities (
  id INTEGER PRIMARY KEY, client_id INTEGER, analysis_id INTEGER,
  titulo TEXT, impacto_x100 INTEGER, esforco TEXT, prioridade TEXT,
  status TEXT NOT NULL DEFAULT 'ABERTA', evidencia_json TEXT,
  criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS strategies (
  id INTEGER PRIMARY KEY, client_id INTEGER, opportunity_id INTEGER,
  titulo TEXT, acao TEXT, responsavel TEXT, prazo TEXT, kpi TEXT,
  status TEXT NOT NULL DEFAULT 'PLANEJADA'
);

CREATE TABLE IF NOT EXISTS prompts (
  id INTEGER PRIMARY KEY, client_id INTEGER,
  gatilho TEXT, contexto_json TEXT, texto TEXT NOT NULL,
  criado_em TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS ai_responses (
  id INTEGER PRIMARY KEY, prompt_id INTEGER REFERENCES prompts(id),
  provedor TEXT NOT NULL DEFAULT 'MANUAL', texto TEXT NOT NULL,
  colado_em TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  avaliacao INTEGER
);

-- ═════════════════════════════════ VIEWS ════════════════════════════════
-- Leitura ergonomica (divisao por 100 num lugar so) e apenas de importacoes
-- vigentes e concluidas — e isso que impede dupla contagem sem apagar historico.

CREATE VIEW IF NOT EXISTS v_vendas AS
SELECT f.id, f.import_id, f.distribuidor_id, f.produto_id, f.pdv_id, f.periodo,
       f.unidades_x100 / 100.0 AS unidades,
       f.valor_x100    / 100.0 AS valor
  FROM fact_sales f
  JOIN imports i ON i.id = f.import_id
 WHERE i.vigente = 1 AND i.status = 'CONCLUIDO';

CREATE VIEW IF NOT EXISTS v_vendas_mensal AS
SELECT a.distribuidor_id, a.produto_id, a.uf, a.periodo, a.n_pdvs,
       a.unidades_x100 / 100.0 AS unidades,
       a.valor_x100    / 100.0 AS valor
  FROM agg_vendas_mensal a
  JOIN imports i ON i.id = a.import_id
 WHERE i.vigente = 1 AND i.status = 'CONCLUIDO';

CREATE VIEW IF NOT EXISTS v_estoque AS
SELECT e.*,
       e.estoque_disp_x100 / 100.0 AS estoque_disp_valor,
       e.media_venda_x100  / 100.0 AS media_venda_valor,
       e.custo_rep_x100    / 100.0 AS custo_reposicao
  FROM fact_inventory e
  JOIN imports i ON i.id = e.import_id
 WHERE i.vigente = 1 AND i.status = 'CONCLUIDO';

CREATE VIEW IF NOT EXISTS v_mercado AS
SELECT m.*,
       m.valor_atual_x100   / 100.0 AS valor_atual,
       m.valor_ant_x100     / 100.0 AS valor_ant,
       m.valor_ytd_x100     / 100.0 AS valor_ytd,
       m.valor_ytd_ant_x100 / 100.0 AS valor_ytd_ant
  FROM fact_market m
  JOIN imports i ON i.id = m.import_id
 WHERE i.vigente = 1 AND i.status = 'CONCLUIDO';
