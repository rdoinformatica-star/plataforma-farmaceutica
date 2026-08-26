-- Fontes de dados reconhecidas pelo sistema (variante PostgreSQL).
-- natureza_elo diz de que elo da cadeia o dado vem — e o que impede comparar
-- preco de varejo (IQVIA) com preco de distribuidor (sell-out).

INSERT INTO data_sources
  (codigo, nome, descricao, natureza_elo, granularidade, unidade_valor) VALUES
  ('SELLOUT',  'Sell-out',
   'Venda do distribuidor para o ponto de venda.',
   'DISTRIBUIDOR_PDV', 'distribuidor x produto x pdv x mes', 'R$'),

  ('IQVIA',    'Mercado Relevante (IQVIA)',
   'Venda do ponto de venda para o consumidor. Mede o mercado, nao o distribuidor.',
   'PDV_CONSUMIDOR', 'mercado x apresentacao x uf x canal x periodo', 'R$'),

  ('ESTOQUE',  'Estoque do distribuidor',
   'Foto do estoque numa data. Nao e serie historica.',
   'ESTOQUE', 'produto x filial x data', 'R$'),

  ('CADASTRO', 'Cadastro de produtos',
   'Tabela de produtos, apresentacoes e codigos.',
   'CADASTRAL', 'produto', NULL),

  ('PDVS',     'Cadastro de PDVs',
   'Tabela de pontos de venda.',
   'CADASTRAL', 'pdv', NULL),

  ('PRECOS',   'Tabela de precos',
   'Precos praticados. O elo da cadeia e obrigatorio em cada linha.',
   'INDEFINIDO', 'produto x uf x periodo', 'R$'),

  ('OUTROS',   'Outros relatorios',
   'Qualquer outra fonte tabular.',
   'INDEFINIDO', NULL, NULL)
ON CONFLICT (codigo) DO NOTHING;
