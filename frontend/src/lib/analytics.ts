/** Tipos e chamadas do motor de performance comercial (Etapa 2). */
import { api } from './api'

export interface Calculo {
  formula: string
  valores?: Record<string, unknown>
  premissas?: string[]
}

export interface Disponibilidade {
  client_id: number
  cliente: string
  distribuidor_ids: number[]
  tem_distribuidor_vinculado: boolean
  tem_sellout: boolean
  tem_iqvia: boolean
  tem_estoque: boolean
  tem_uf: boolean
  tem_pdv: boolean
  periodo_min: number | null
  periodo_max: number | null
  n_produtos: number
  n_pdvs: number
  motivo_indisponivel: string | null
}

interface Indisponivel {
  disponivel: false
  motivo: string
}

export interface Comparacao {
  rotulo: string
  comparacao_valida: boolean
  periodo_atual: { ini: number; fim: number; label: string }
  periodo_anterior: { ini: number; fim: number; label: string }
  faturamento_atual: number
  faturamento_anterior: number | null
  faturamento_variacao_pct: number | null
  faturamento_variacao_rs: number | null
  unidades_atual: number
  unidades_anterior: number | null
  unidades_variacao_pct: number | null
  calculo: Calculo
}

export type Resumo =
  | Indisponivel
  | {
      disponivel: true
      cliente: string
      periodo: { ini: number; fim: number; label: string }
      faturamento: number
      unidades: number
      n_produtos: number
      n_pdvs: number
      comparacao_periodo_anterior: Comparacao
      comparacao_ano_anterior: Comparacao | null
      calculo: Calculo
    }

export type EvolucaoMensal =
  | Indisponivel
  | {
      disponivel: true
      metrica: string
      serie: { periodo: number; label: string; valor: number }[]
      calculo: Calculo
    }

export interface ItemProduto {
  produto_id: number
  produto: string
  faturamento_atual: number
  unidades_atual: number
  faturamento_anterior: number
  variacao_pct: number | null
  participacao_pct: number | null
}

export type RankingProdutos =
  | Indisponivel
  | {
      disponivel: true
      total: number
      ordenar: string
      comparacao_valida?: boolean
      itens: ItemProduto[]
      calculo: Calculo
    }

export interface ItemVariacao extends ItemProduto {
  classificacao: 'NOVO' | 'CRESCIMENTO' | 'ATENCAO' | 'QUEDA' | 'QUEDA_CRITICA'
  faturamento_variacao_rs: number
}

export type VariacaoProdutos =
  | Indisponivel
  | {
      disponivel: true
      direcao: 'crescimento' | 'queda'
      limites: Record<string, number>
      itens: ItemVariacao[]
      calculo: Calculo
    }

export interface ItemUF {
  uf: string
  faturamento: number
  unidades: number
  participacao_pct: number | null
  variacao_pct: number | null
}

export type AnaliseUF =
  | Indisponivel
  | { disponivel: true; itens: ItemUF[]; comparacao_valida?: boolean; calculo: Calculo }

export interface ItemPDV {
  pdv_id: number
  pdv: string
  faturamento?: number
  unidades?: number
  n_skus?: number
  participacao_pct?: number | null
  variacao_pct?: number | null
}

export type RankingPDVs =
  | Indisponivel
  | {
      disponivel: true
      visao: 'ranking' | 'novos' | 'sumidos'
      total: number
      uf?: string | null
      faturamento_total?: number
      comparacao_valida?: boolean
      itens: ItemPDV[]
      calculo: Calculo
    }

/* Potencial — duas bases de comparação diferentes, ver analytics/potencial.py */

export interface ItemPotencialProduto {
  produto_id: number
  produto: string
  mercado: string | null
  nivel_ligacao: string
  faturamento_atual: number
  unidades_atual: number
  mercado_un: number
  penetracao_pct: number
  penetracao_referencia_pct: number
  indice: number | null
  unidades_alvo: number
  potencial_un: number
  preco_medio: number
  potencial_valor: number
  share_industria_pct: number | null
}

export interface ContextoMolecula {
  produto_id: number
  produto: string
  mercado: string | null
  referencia_mercado: string
  faturamento_atual: number
  unidades_atual: number
  mercado_molecula_un: number
  penetracao_na_molecula_pct: number
}

export type PotencialProdutos =
  | Indisponivel
  | {
      disponivel: true
      uf: string | null
      penetracao_referencia_pct: number
      n_skus: number
      n_skus_fora: number
      n_so_molecula: number
      contexto_molecula: ContextoMolecula[]
      n_sem_correspondencia: number
      cobertura_da_ponte_pct: number | null
      potencial_total: number
      itens: ItemPotencialProduto[]
      calculo: Calculo
    }

export interface ItemPotencialPDV {
  pdv_id: number
  pdv: string
  uf: string | null
  faturamento_atual: number
  n_skus: number
  faixa_atual: string
  faixa_alvo: string
  mix_alvo: number
  skus_a_ganhar: number
  rs_por_sku_referencia: number
  potencial_valor: number
  indice: number | null
}

export interface PerfilFaixaMix {
  faixa: string
  indice: number
  n_pdvs: number
  mix_mediano: number
  rs_por_sku_mediano: number
  rs_por_pdv_mediano: number
}

export type PotencialPDVs =
  | Indisponivel
  | {
      disponivel: true
      uf: string | null
      n_pdvs_avaliados: number
      n_pdvs_com_potencial: number
      n_pdvs_sem_referencia: number
      potencial_total: number
      perfil_faixas: PerfilFaixaMix[]
      itens: ItemPotencialPDV[]
      calculo: Calculo
    }

export interface FaixaConcentracao {
  top: number
  valor: number
  percentual: number | null
  n_elementos: number
}

export type Concentracao =
  | Indisponivel
  | {
      disponivel: true
      contexto: string
      n_total_elementos: number
      faturamento_total: number
      faixas: FaixaConcentracao[]
      calculo: Calculo
    }

export interface Alerta {
  tipo: 'verde' | 'vermelho' | 'amarelo' | 'azul'
  categoria: string
  texto: string
  produto_id: number
  valor_pct: number | null
}

export type Alertas = Indisponivel | { disponivel: true; itens: Alerta[]; n_total: number; calculo: Calculo }

/* ─────────────────────────── Etapa 3 ─────────────────────────── */

export interface ItemABC extends ItemProduto {
  classe_abc: 'A' | 'B' | 'C'
  participacao_acumulada_pct: number
  pdvs_compradores?: number
  cobertura_pct?: number | null
}

export interface FaixaResumoABC {
  n_produtos: number
  pct_produtos: number
  faturamento: number
  pct_faturamento: number
}

export type CurvaABC =
  | Indisponivel
  | {
      disponivel: true
      n_total_produtos: number
      faturamento_total: number
      limite_a: number
      limite_b: number
      uf: string | null
      resumo: { A: FaixaResumoABC; B: FaixaResumoABC; C: FaixaResumoABC }
      itens: ItemABC[]
      calculo: Calculo
    }

/* ABC do cliente x ABC da Vitamedic no mercado (IQVIA) */

export interface ItemABCMercado {
  produto_id: number
  produto: string
  faturamento_cliente: number
  participacao_cliente_pct: number | null
  acumulada_cliente_pct: number
  classe_cliente: 'A' | 'B' | 'C'
  valor_mercado: number
  participacao_mercado_pct: number
  acumulada_mercado_pct: number
  classe_mercado: 'A' | 'B' | 'C'
  posicao_mercado: number
  distancia_classes: number
  situacao: 'OPORTUNIDADE' | 'EM_LINHA' | 'ACIMA_DO_MERCADO'
  share_no_vitamedic_pct: number | null
  variacao_pct: number | null
}

export interface PontoCurva {
  posicao: number
  acumulada_pct: number
}

export type ABCMercado =
  | Indisponivel
  | {
      disponivel: true
      uf: string | null
      limite_a: number
      limite_b: number
      n_ligados: number
      n_sem_correspondencia: number
      cobertura_da_ponte_pct: number | null
      faturamento_cliente_ligado: number
      valor_mercado_total: number
      share_no_vitamedic_pct: number | null
      por_situacao: Record<string, number>
      n_produtos_mercado: number
      curva_cliente: PontoCurva[]
      curva_mercado: PontoCurva[]
      oportunidades: ItemABCMercado[]
      itens: ItemABCMercado[]
      sem_correspondencia: {
        produto_id: number
        produto: string
        faturamento: number
        classe_cliente: string
      }[]
      calculo: Calculo
    }

export interface ItemMatrizABC {
  produto_id: number
  produto: string
  faturamento_atual: number
  variacao_pct: number | null
}

export type FaixaCrescimento = 'CRESCENDO' | 'ESTAVEL' | 'CAINDO' | 'NOVO' | 'SEM_HISTORICO'

export type ABCCrescimento =
  | Indisponivel
  | {
      disponivel: true
      comparacao_valida: boolean
      contagem: Record<'A' | 'B' | 'C', Record<FaixaCrescimento, number>>
      matriz: Record<'A' | 'B' | 'C', Record<FaixaCrescimento, ItemMatrizABC[]>>
      calculo: Calculo
    }

export interface ItemCobertura extends ItemProduto {
  pdvs_compradores: number
  pdvs_base: number
  cobertura_pct: number
}

export type Cobertura =
  | Indisponivel
  | {
      disponivel: true
      pdvs_base: number
      uf: string | null
      total: number
      itens: ItemCobertura[]
      calculo: Calculo
    }

export interface ItemMatrizCobertura extends ItemCobertura {
  quadrante: 'PRIORITARIO' | 'CONSOLIDADO' | 'INVESTIGAR_PRODUTIVIDADE' | 'BAIXA_PRIORIDADE'
}

export type MatrizCobertura =
  | Indisponivel
  | {
      disponivel: true
      itens: ItemMatrizCobertura[]
      resumo: Record<string, number>
      mediana_faturamento: number
      mediana_cobertura_pct: number
      calculo: Calculo
    }

export interface ItemPotencial {
  produto_id: number
  produto: string
  faturamento_atual: number
  pdvs_compradores: number
  cobertura_pct: number
  rs_por_pdv: number
  potencial_estimado: number
}

export type PotencialCobertura =
  | Indisponivel
  | {
      disponivel: true
      incremento_pp: number
      top_n: number
      pdvs_base: number
      pdvs_incremento: number
      potencial_estimado_total: number
      potencial_estimado_anual: number
      itens: ItemPotencial[]
      sem_dado_suficiente: { produto_id: number; produto: string; pdvs_compradores: number }[]
      calculo: Calculo
    }

export interface FaixaMix {
  faixa: string
  sku_min: number
  sku_max: number | null
  n_pdvs: number
  pct_pdvs: number
  faturamento: number
  pct_faturamento: number
  rs_por_pdv: number | null
}

export type Mix =
  | Indisponivel
  | {
      disponivel: true
      total_pdvs: number
      mix_medio: number
      mix_mediano: number
      uf: string | null
      resumo: FaixaMix[]
      calculo: Calculo
    }

export interface ProdutoDaFaixa {
  produto_id: number
  produto: string
  n_pdvs: number
  pct_da_faixa: number
  faturamento: number
}

export interface PDVDaFaixa {
  pdv_id: number
  pdv: string
  uf: string | null
  faturamento: number
  unidades: number
  n_skus: number
}

/** Drill-down de uma faixa de mix — generaliza Monoproduto para qualquer
 * intervalo de SKUs (1, 2-3, 4-9, 10+ ou recorte arbitrário). */
export type DetalheFaixaMix =
  | Indisponivel
  | {
      disponivel: true
      faixa: string
      sku_min: number
      sku_max: number | null
      uf: string | null
      n_pdvs: number
      faturamento: number
      participacao_pct: number
      rs_por_pdv: number | null
      mix_medio?: number
      n_mostrados?: number
      top_produtos: ProdutoDaFaixa[]
      itens: PDVDaFaixa[]
      calculo: Calculo
    }

export type Monoproduto =
  | Indisponivel
  | {
      disponivel: true
      n_pdvs: number
      faturamento: number
      rs_por_pdv: number | null
      top_produtos: { produto_id: number; produto: string; n_pdvs: number }[]
      itens: { pdv_id: number; pdv: string; faturamento: number; produto_id: number | null; produto: string }[]
      calculo: Calculo
    }

export type AltoMix =
  | Indisponivel
  | {
      disponivel: true
      n_pdvs: number
      faturamento: number
      participacao_pct: number
      rs_por_pdv: number | null
      itens: { pdv_id: number; pdv: string; faturamento: number; n_skus: number }[]
      calculo: Calculo
    }

export interface ItemExpansaoMix {
  pdv_id: number
  pdv: string
  n_skus_atual: number
  faixa_atual: string
  faixa_referencia: string
  faturamento_atual: number
  rs_por_pdv_faixa_referencia: number
}

export type ExpansaoMix =
  | Indisponivel
  | { disponivel: true; total: number; itens: ItemExpansaoMix[]; calculo: Calculo }

export interface ItemOportunidade {
  tipo: 'ABC_QUEDA' | 'COBERTURA' | 'MIX' | 'CONCENTRACAO'
  oportunidade: string
  fonte: string
  potencial_estimado: number
  impacto_pct: number
  facilidade: number
  score: number
  prioridade: 'Alta' | 'Média' | 'Baixa'
  premissa: string
  rotulo: 'FATO'
  referencia_id: number | null
}

export type MatrizOportunidades =
  | Indisponivel
  | {
      disponivel: true
      total: number
      uf?: string | null
      escopo?: 'PRODUTO' | 'PDV' | null
      por_escopo?: { PRODUTO: number; PDV: number }
      itens: ItemOportunidade[]
      pesos?: { potencial: number; impacto: number; facilidade: number }
      calculo: Calculo
    }

export type AlertasExpandidos = Indisponivel | { disponivel: true; itens: Alerta[]; n_total: number; calculo: Calculo }

/* Sugestão de pedido de compra — ver analytics/compra.py */

export type Agrupamento = 'abc' | 'estoque' | 'marca'

export interface LinhaPedido {
  produto_id: number
  produto: string
  grupo: string
  classe_estoque: string | null
  filiais: string[]
  estoque_atual_un: number
  pendencia_un: number
  venda_dia: number
  venda_mes: number
  dde_atual: number | null
  dde_alvo: number
  dde_origem: 'produto' | 'grupo' | 'padrao'
  estoque_alvo_un: number
  sugestao_un: number
  custo_unitario: number
  sugestao_valor: number
  dde_apos_pedido: number | null
  limitado_por_teto?: boolean
  sugestao_valor_cheio?: number
  excedeu_teto_na_redistribuicao?: boolean
}

export interface GrupoPedido {
  grupo: string
  skus: number
  unidades: number
  valor: number
  dde_alvo: number
}

export interface CortePedido {
  valor_alvo: number
  necessidade_total: number
  atendido: number
  sobra_do_orcamento: number
  necessidade_nao_atendida: number
  teto_por_sku_pct: number
  teto_por_sku_valor: number
  n_limitados_por_teto: number
  n_redistribuidos_acima_do_teto: number
  avisos: string[]
}

export type SugestaoPedido =
  | Indisponivel
  | {
      disponivel: true
      data_ref: string
      agrupamento: Agrupamento
      base_velocidade: string
      filial: string | null
      dde_padrao: number
      dde_por_grupo: Record<string, number>
      n_skus: number
      n_sem_giro: number
      n_sem_ligacao: number
      valor_sem_ligacao: number
      grupo_sem_ligacao: string
      total_unidades: number
      total_valor: number
      necessidade_total: number
      corte: CortePedido | null
      grupos: GrupoPedido[]
      grupos_disponiveis: string[]
      itens: LinhaPedido[]
      calculo: Calculo
    }

export interface EntradaPedido {
  periodo_ini: number
  periodo_fim: number
  agrupamento?: Agrupamento
  dde_padrao?: number
  dde_por_grupo?: Record<string, number>
  dde_por_produto?: Record<number, number>
  base_velocidade?: string
  filial?: string | null
  valor_alvo?: number | null
  teto_por_sku?: number
  incluir_sem_giro?: boolean
}

/* Combos, afinidade e ajuste de preço — ver analytics/combos.py */

export type FocoCombo = 'geral' | 'criticos' | 'zumbi' | 'misto' | 'giro_rapido'

export interface Acompanhante {
  produto_id: number
  produto: string
  pdvs_ambos: number
  cobertura_pdvs: number
  lift: number
  confianca_pct: number
  recorrencia: number | null
  uso_continuo: boolean
  dde: number | null
  classe_estoque: string | null
  estoque_un: number | null
  estoque_valor: number | null
}

export interface Combo {
  puxador_id: number
  puxador: string
  puxador_cobertura_pdvs: number
  puxador_dde: number | null
  puxador_classe_estoque: string | null
  puxador_recorrencia: number | null
  acompanhantes: Acompanhante[]
  n_acompanhantes: number
  lift_medio: number
  capital_parado_no_combo: number
  tem_uso_continuo: boolean
}

export type SugestaoCombos =
  | Indisponivel
  | {
      disponivel: true
      foco: FocoCombo
      uf: string | null
      tem_estoque: boolean
      total: number
      capital_parado_alcancado: number
      itens: Combo[]
      calculo: Calculo
    }

/* Kits tematicos (grupos de 3+ produtos, nao so pares) — ver kits_tematicos() */

export interface ProdutoKit {
  produto_id: number
  produto: string
}

export interface MesKit {
  mes: number
  mes_nome: string
  valor: number
}

export interface Kit {
  produtos: ProdutoKit[]
  tamanho: number
  afinidade_media: number
  faturamento_periodo_selecionado: number
  faturamento_total_historico: number
  picos_mes: number[]
  picos_mes_nome: string[]
  distribuicao_por_mes: MesKit[]
}

export type Kits =
  | Indisponivel
  | {
      disponivel: true
      uf: string | null
      n_kits: number
      n_anos_historico: number
      periodo_historico: { min: number | null; max: number | null }
      itens: Kit[]
      calculo: Calculo
    }

export interface ItemAjustePreco {
  produto_id: number
  produto: string
  preco_cliente: number
  preco_outros: number
  diferenca_pct: number
  ajuste_sugerido_pct: number
  preco_alvo: number
  unidades_cliente: number
  faturamento_cliente: number
  receita_cedida_no_volume_atual: number
  dde: number | null
  classe_estoque: string | null
  estoque_valor: number | null
  prioridade: 'ALTA' | 'MEDIA' | 'BAIXA'
}

export type AjustePreco =
  | Indisponivel
  | {
      disponivel: true
      uf: string | null
      limite_alerta_pct: number
      n_produtos: number
      n_sem_volume: number
      receita_cedida_total: number
      itens: ItemAjustePreco[]
      calculo: Calculo
    }

/* ── Etapa 4: estoque, mercado/IQVIA e preço ─────────────────────────────── */

export interface FilialEstoque {
  filial: string
  linhas: number
  com_posicao: number
  com_valor: number
  com_media_venda: number
  tem_posicao_fisica: boolean
}

export type PerfilEstoque =
  | Indisponivel
  | {
      disponivel: true
      linhas: number
      produtos: number
      com_posicao: number
      sem_posicao: number
      com_valor: number
      com_media_venda: number
      data_ref: string
      n_datas: number
      eh_foto: boolean
      por_filial: FilialEstoque[]
      filiais_vinculadas: Record<string, number>
      calculo: Calculo
    }

export interface ItemEstoque {
  produto_id: number
  produto: string
  filial: string
  estoque_total_un: number | null
  estoque_disp_un: number
  valor_estoque: number
  custo_reposicao: number | null
  media_venda_mes_fonte: number | null
  venda_dia_fonte: number | null
  venda_dia_periodo: number | null
  dde_fonte: number | null
  dde_periodo: number | null
  dde: number | null
  cobertura_dias_origem: number | null
  classificacao: string
  sem_venda: boolean
  motivo_dde_indefinido: string | null
  faturamento?: number
  quadrante?: string
  quadrante_descricao?: string
}

export interface FaixaCobertura {
  de: number
  ate: number | null
  rotulo: string
}

export type PosicaoEstoque =
  | Indisponivel
  | {
      disponivel: true
      data_ref: string
      base_velocidade: string
      filial: string | null
      classe: string | null
      n_total_sem_filtro: number
      itens: ItemEstoque[]
      faixas: FaixaCobertura[]
      calculo: Calculo
    }

export type ResumoEstoque =
  | Indisponivel
  | {
      disponivel: true
      data_ref: string
      valor_total: number
      skus_com_estoque: number
      skus_sem_venda: number
      skus_dde_indefinido: number
      cobertura_media_dias: number | null
      cobertura_ponderada_dias: number | null
      cobertura_portfolio_dias: number | null
      demanda_diaria_valor: number
      skus_acima_180: number
      valor_acima_180: number
      skus_acima_365: number
      valor_acima_365: number
      por_classe: { classe: string; skus: number; valor: number }[]
      calculo: Calculo
    }

export type EstoqueZumbi =
  | Indisponivel
  | {
      disponivel: true
      limite_dias: number
      n_skus: number
      valor_total: number
      itens: ItemEstoque[]
      calculo: Calculo
    }

export type CapitalParado =
  | Indisponivel
  | {
      disponivel: true
      valor_total_estoque: number
      faixas: {
        acima_de_dias: number
        skus: number
        valor: number
        pct_do_estoque: number | null
      }[]
      calculo: Calculo
    }

export interface ItemSimulacao {
  produto_id: number
  produto: string
  filial: string
  estoque_atual_un: number
  estoque_objetivo_un: number
  excesso_un: number
  valor_estoque: number
  excesso_valor: number
  dde: number | null
  sem_giro: boolean
}

export type SimuladorEstoque =
  | Indisponivel
  | {
      disponivel: true
      objetivo_dias: number
      valor_estoque_atual: number
      capital_potencialmente_liberavel: number
      pct_do_estoque: number | null
      n_skus_com_excesso: number
      itens: ItemSimulacao[]
      calculo: Calculo
    }

export type MatrizEstoque =
  | Indisponivel
  | {
      disponivel: true
      mediana_dde: number
      mediana_faturamento: number
      quadrantes: {
        quadrante: string
        descricao: string
        skus: number
        valor_estoque: number
        faturamento: number
      }[]
      itens: ItemEstoque[]
      calculo: Calculo
    }

export type PerfilMercado =
  | Indisponivel
  | {
      disponivel: true
      linhas: number
      abas: number
      periodos: number
      periodo_ref: number
      eh_foto_unica: boolean
      janela_ytd: { ini: number; fim: number; ini_ant: number; fim_ant: number }
      dimensoes: Record<string, number>
      linhas_vitamedic: number
      produto_id_preenchido: number
      tem_ligacao_com_dim_product: boolean
      identifica_distribuidor: boolean
      calculo: Calculo
    }

export type ResumoMercado =
  | Indisponivel
  | {
      disponivel: true
      recorte: Record<string, string | null>
      linhas: number
      unidades_ytd: number
      valor_ytd: number
      unidades_ytd_ant: number
      valor_ytd_ant: number
      cresc_unidades_pct: number | null
      cresc_valor_pct: number | null
      unidades_mes: number
      valor_mes: number
      cresc_mes_valor_pct: number | null
      janela: { ini: number; fim: number; ini_ant: number; fim_ant: number }
      calculo: Calculo
    }

export type ShareIndustria =
  | Indisponivel
  | {
      disponivel: true
      escopo: string
      base: string
      recorte: Record<string, string | null>
      vitamedic: number
      mercado_total: number
      share_pct: number
      share_ant_pct: number | null
      delta_share_pp: number | null
      calculo: Calculo
    }

export interface ShareCliente {
  disponivel: false
  motivo: string
  alternativa?: string
  ocorrencias_do_nome_no_mercado?: number
}

export interface ItemMercadoUf {
  uf: string
  mercado_un: number
  mercado_valor: number
  vitamedic_un: number
  share_pct: number
  share_ant_pct: number | null
  delta_share_pp: number | null
  cresc_mercado_pct: number | null
}

export type MercadoRegional =
  | Indisponivel
  | { disponivel: true; recorte: Record<string, string | null>; itens: ItemMercadoUf[]; calculo: Calculo }

export interface ItemRankingMercado {
  mercado: string
  vitamedic_un: number
  mercado_un: number
  mercado_valor: number
  share_pct: number
  share_ant_pct: number | null
  delta_share_pp: number | null
  cresc_mercado_un_pct: number | null
  cresc_vitamedic_un_pct: number | null
}

export type RankingMercados =
  | Indisponivel
  | { disponivel: true; n_mercados: number; itens: ItemRankingMercado[]; calculo: Calculo }

export type ClienteVsMercado =
  | Indisponivel
  | {
      disponivel: true
      janela: { ini: number; fim: number; ini_ant: number; fim_ant: number }
      recorte: Record<string, string | null>
      cliente: {
        valor: number
        valor_ant: number
        cresc_valor_pct: number | null
        unidades: number
        unidades_ant: number
        cresc_unidades_pct: number | null
      }
      mercado: {
        valor: number
        valor_ant: number
        cresc_valor_pct: number | null
        unidades: number
        unidades_ant: number
        cresc_unidades_pct: number | null
      }
      diferenca_valor_pp: number | null
      diferenca_unidades_pp: number | null
      leitura_valor: string | null
      leitura_unidades: string | null
      calculo: Calculo
    }

export interface ItemPonte {
  produto_id: number
  produto: string
  mercado: string
  nivel_ligacao: 'apresentacao' | 'molecula'
  referencia_mercado: string
  faturamento_cliente: number
  unidades_cliente: number
  mercado_un: number
  vitamedic_un: number
  share_industria_pct: number
  share_industria_ant_pct: number | null
  delta_share_pp: number | null
}

export type PonteMercado =
  | Indisponivel
  | {
      disponivel: true
      n_ligados: number
      n_sem_correspondencia: number
      por_nivel: { nivel: string; skus: number; faturamento: number }[]
      faturamento_ligado: number
      faturamento_sem_correspondencia: number
      cobertura_da_ponte_pct: number | null
      itens: ItemPonte[]
      sem_correspondencia: { produto_id: number; produto: string; faturamento: number }[]
      calculo: Calculo
    }

export type Comparabilidade =
  | Indisponivel
  | {
      disponivel: true
      fontes: {
        fonte: string
        disponivel: boolean
        elo: string
        unidade: string
        periodo: string
        produto: string
        observacao: string
      }[]
      pares: { de: string; para: string; comparavel: boolean; motivo: string }[]
      calculo: Calculo
    }

export interface ItemPreco {
  produto_id: number
  produto: string
  preco_cliente: number
  preco_outros: number
  diferenca_pct: number | null
  unidades_cliente: number
  unidades_outros: number
  faturamento_cliente: number
  posicao: 'ACIMA' | 'ABAIXO' | 'EM_LINHA' | null
}

export type PrecoVsConcorrentes =
  | Indisponivel
  | {
      disponivel: true
      uf: string | null
      minimo_unidades: number
      limite_alerta_pct: number
      n_comparaveis: number
      n_sem_volume: number
      preco_medio_cliente: number | null
      preco_medio_outros: number | null
      itens: ItemPreco[]
      sem_volume: {
        produto_id: number
        produto: string
        unidades_cliente: number
        unidades_outros: number
        motivo: string
      }[]
      calculo: Calculo
    }

export type EvolucaoPreco =
  | Indisponivel
  | {
      disponivel: true
      produto_id: number | null
      uf: string | null
      serie: { periodo: number; unidades: number; valor: number; preco_medio: number | null }[]
      preco_inicial: number | null
      preco_final: number | null
      variacao_pct: number | null
      calculo: Calculo
    }

export type PrecoVarejo =
  | Indisponivel
  | {
      disponivel: true
      escopo: string
      recorte: Record<string, string | null>
      n_mercados: number
      itens: {
        mercado: string
        preco_vitamedic: number
        lider: string
        preco_lider: number
        indice_vs_lider_pct: number | null
        concorrentes: number
        concorrentes_mais_baratos: number
        unidades_vitamedic: number
      }[]
      calculo: Calculo
    }

const q = (params: Record<string, string | number | undefined>) =>
  '?' +
  Object.entries(params)
    .filter(([, v]) => v !== undefined)
    .map(([k, v]) => `${k}=${encodeURIComponent(v!)}`)
    .join('&')

/** Baixa um arquivo binário (planilha) e dispara o download no navegador.
 * Usado por toda exportação em .xlsx — a resposta não é JSON, então não
 * passa por api.get/post. */
async function _baixarArquivo(url: string, init: RequestInit | undefined, nomePadrao: string) {
  const r = await fetch(url, init)
  if (!r.ok) {
    const corpo = await r.json().catch(() => ({}))
    throw new Error(corpo?.erro?.mensagem ?? 'Não foi possível gerar a planilha.')
  }
  const blob = await r.blob()
  // O nome vem do Content-Disposition do servidor, que já inclui cliente e data.
  const cd = r.headers.get('content-disposition') ?? ''
  const nome = /filename="([^"]+)"/.exec(cd)?.[1] ?? nomePadrao
  const objUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objUrl
  a.download = nome
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(objUrl)
  return nome
}

export const analytics = {
  disponibilidade: (cid: number) => api.get<Disponibilidade>(`/analytics/${cid}/disponibilidade`),

  resumo: (cid: number, ini: number, fim: number) =>
    api.get<Resumo>(`/analytics/${cid}/resumo${q({ periodo_ini: ini, periodo_fim: fim })}`),

  evolucaoMensal: (cid: number, ini: number, fim: number, metrica: string) =>
    api.get<EvolucaoMensal>(
      `/analytics/${cid}/evolucao-mensal${q({ periodo_ini: ini, periodo_fim: fim, metrica })}`,
    ),

  produtos: (
    cid: number, ini: number, fim: number, ordenar: string,
    limite = 20, offset = 0, uf?: string,
  ) =>
    api.get<RankingProdutos>(
      `/analytics/${cid}/produtos${q({ periodo_ini: ini, periodo_fim: fim, ordenar, uf, limite, offset })}`,
    ),

  produtosVariacao: (cid: number, ini: number, fim: number, direcao: 'crescimento' | 'queda') =>
    api.get<VariacaoProdutos>(
      `/analytics/${cid}/produtos/variacao${q({ periodo_ini: ini, periodo_fim: fim, direcao })}`,
    ),

  uf: (cid: number, ini: number, fim: number) =>
    api.get<AnaliseUF>(`/analytics/${cid}/uf${q({ periodo_ini: ini, periodo_fim: fim })}`),

  pdvs: (
    cid: number, ini: number, fim: number,
    visao: 'ranking' | 'novos' | 'sumidos', limite = 20, uf?: string,
  ) =>
    api.get<RankingPDVs>(
      `/analytics/${cid}/pdvs${q({ periodo_ini: ini, periodo_fim: fim, visao, uf, limite })}`,
    ),

  potencialProdutos: (cid: number, ini: number, fim: number, uf?: string, topN = 200) =>
    api.get<PotencialProdutos>(
      `/analytics/${cid}/potencial/produtos${q({ periodo_ini: ini, periodo_fim: fim, uf, top_n: topN })}`,
    ),

  potencialPdvs: (cid: number, ini: number, fim: number, uf?: string, topN = 200) =>
    api.get<PotencialPDVs>(
      `/analytics/${cid}/potencial/pdvs${q({ periodo_ini: ini, periodo_fim: fim, uf, top_n: topN })}`,
    ),

  concentracao: (cid: number, ini: number, fim: number, contexto: 'produtos' | 'pdvs') =>
    api.get<Concentracao>(
      `/analytics/${cid}/concentracao${q({ periodo_ini: ini, periodo_fim: fim, contexto })}`,
    ),

  alertas: (cid: number, ini: number, fim: number) =>
    api.get<Alertas>(`/analytics/${cid}/alertas${q({ periodo_ini: ini, periodo_fim: fim })}`),

  // Etapa 3
  abc: (cid: number, ini: number, fim: number, limiteA = 80, limiteB = 95, uf?: string) =>
    api.get<CurvaABC>(
      `/analytics/${cid}/abc${q({ periodo_ini: ini, periodo_fim: fim, limite_a: limiteA, limite_b: limiteB, uf })}`,
    ),

  abcMercado: (cid: number, ini: number, fim: number, limiteA = 80, limiteB = 95, uf?: string) =>
    api.get<ABCMercado>(
      `/analytics/${cid}/abc/mercado${q({ periodo_ini: ini, periodo_fim: fim, limite_a: limiteA, limite_b: limiteB, uf })}`,
    ),

  abcCrescimento: (cid: number, ini: number, fim: number, uf?: string) =>
    api.get<ABCCrescimento>(
      `/analytics/${cid}/abc/crescimento${q({ periodo_ini: ini, periodo_fim: fim, uf })}`,
    ),

  cobertura: (cid: number, ini: number, fim: number, uf?: string, limite = 100) =>
    api.get<Cobertura>(
      `/analytics/${cid}/cobertura${q({ periodo_ini: ini, periodo_fim: fim, uf, limite })}`,
    ),

  coberturaMatriz: (cid: number, ini: number, fim: number, uf?: string) =>
    api.get<MatrizCobertura>(
      `/analytics/${cid}/cobertura/matriz${q({ periodo_ini: ini, periodo_fim: fim, uf })}`,
    ),

  coberturaPotencial: (cid: number, ini: number, fim: number, incrementoPp = 10, uf?: string) =>
    api.get<PotencialCobertura>(
      `/analytics/${cid}/cobertura/potencial${q({ periodo_ini: ini, periodo_fim: fim, incremento_pp: incrementoPp, uf })}`,
    ),

  mix: (cid: number, ini: number, fim: number, uf?: string) =>
    api.get<Mix>(`/analytics/${cid}/mix${q({ periodo_ini: ini, periodo_fim: fim, uf })}`),

  mixMonoproduto: (cid: number, ini: number, fim: number, uf?: string) =>
    api.get<Monoproduto>(
      `/analytics/${cid}/mix/monoproduto${q({ periodo_ini: ini, periodo_fim: fim, uf })}`,
    ),

  mixFaixa: (
    cid: number, ini: number, fim: number,
    skuMin: number, skuMax?: number, uf?: string, limite = 200,
  ) =>
    api.get<DetalheFaixaMix>(
      `/analytics/${cid}/mix/faixa${q({ periodo_ini: ini, periodo_fim: fim, sku_min: skuMin, sku_max: skuMax, uf, limite })}`,
    ),

  mixAlto: (cid: number, ini: number, fim: number, minimoSkus = 10, uf?: string) =>
    api.get<AltoMix>(
      `/analytics/${cid}/mix/alto${q({ periodo_ini: ini, periodo_fim: fim, minimo_skus: minimoSkus, uf })}`,
    ),

  mixOportunidades: (cid: number, ini: number, fim: number, uf?: string) =>
    api.get<ExpansaoMix>(
      `/analytics/${cid}/mix/oportunidades${q({ periodo_ini: ini, periodo_fim: fim, uf })}`,
    ),

  oportunidades: (
    cid: number,
    ini: number,
    fim: number,
    pesoPotencial = 40,
    pesoImpacto = 35,
    pesoFacilidade = 25,
    uf?: string,
    escopo?: 'PRODUTO' | 'PDV',
  ) =>
    api.get<MatrizOportunidades>(
      `/analytics/${cid}/oportunidades${q({
        periodo_ini: ini,
        periodo_fim: fim,
        peso_potencial: pesoPotencial,
        peso_impacto: pesoImpacto,
        peso_facilidade: pesoFacilidade,
        uf,
        escopo,
      })}`,
    ),

  compra: (cid: number, entrada: EntradaPedido) =>
    api.post<SugestaoPedido>(`/analytics/${cid}/compra`, entrada),

  /** Baixa a proposta em .xlsx. Não passa por api.post: a resposta é binária,
   * não JSON, e precisa virar um download no navegador. */
  compraXlsx: (cid: number, entrada: EntradaPedido) =>
    _baixarArquivo(`/api/analytics/${cid}/compra/xlsx`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(entrada),
    }, 'proposta_compra.xlsx'),

  abcXlsx: (cid: number, ini: number, fim: number, limiteA = 80, limiteB = 95, uf?: string) =>
    _baixarArquivo(
      `/api/analytics/${cid}/abc/xlsx${q({ periodo_ini: ini, periodo_fim: fim, limite_a: limiteA, limite_b: limiteB, uf })}`,
      undefined, 'curva_abc.xlsx',
    ),

  oportunidadesXlsx: (
    cid: number, ini: number, fim: number,
    pesoPotencial = 40, pesoImpacto = 35, pesoFacilidade = 25,
    uf?: string, foco: FocoCombo = 'geral',
  ) =>
    _baixarArquivo(
      `/api/analytics/${cid}/oportunidades/xlsx${q({
        periodo_ini: ini, periodo_fim: fim, peso_potencial: pesoPotencial,
        peso_impacto: pesoImpacto, peso_facilidade: pesoFacilidade, uf, foco,
      })}`,
      undefined, 'oportunidades.xlsx',
    ),

  combos: (
    cid: number, ini: number, fim: number,
    foco: FocoCombo = 'geral', uf?: string, maxAcompanhantes = 2, topN = 20,
  ) =>
    api.get<SugestaoCombos>(
      `/analytics/${cid}/combos${q({
        periodo_ini: ini, periodo_fim: fim, foco, uf,
        max_acompanhantes: maxAcompanhantes, top_n: topN,
      })}`,
    ),

  combosKits: (cid: number, ini: number, fim: number, uf?: string, topN = 15) =>
    api.get<Kits>(
      `/analytics/${cid}/combos/kits${q({ periodo_ini: ini, periodo_fim: fim, uf, top_n: topN })}`,
    ),

  ajustePreco: (cid: number, ini: number, fim: number, uf?: string, topN = 30) =>
    api.get<AjustePreco>(
      `/analytics/${cid}/ajuste-preco${q({ periodo_ini: ini, periodo_fim: fim, uf, top_n: topN })}`,
    ),

  alertasExpandidos: (cid: number, ini: number, fim: number) =>
    api.get<AlertasExpandidos>(
      `/analytics/${cid}/alertas-expandidos${q({ periodo_ini: ini, periodo_fim: fim })}`,
    ),

  estoquePerfil: (cid: number) =>
    api.get<PerfilEstoque>(`/analytics/${cid}/estoque/perfil`),

  estoque: (
    cid: number, ini: number, fim: number, base = 'fonte',
    filial?: string, limite = 500, classe?: string,
  ) =>
    api.get<PosicaoEstoque>(
      `/analytics/${cid}/estoque${q({ periodo_ini: ini, periodo_fim: fim, base_velocidade: base, filial, classe, limite })}`,
    ),

  estoqueResumo: (cid: number, ini: number, fim: number, base = 'fonte', filial?: string) =>
    api.get<ResumoEstoque>(
      `/analytics/${cid}/estoque/resumo${q({ periodo_ini: ini, periodo_fim: fim, base_velocidade: base, filial })}`,
    ),

  estoqueZumbi: (cid: number, ini: number, fim: number, limiteDias = 365, base = 'fonte', filial?: string) =>
    api.get<EstoqueZumbi>(
      `/analytics/${cid}/estoque/zumbi${q({ periodo_ini: ini, periodo_fim: fim, limite_dias: limiteDias, base_velocidade: base, filial })}`,
    ),

  estoqueCapital: (cid: number, ini: number, fim: number, base = 'fonte', filial?: string) =>
    api.get<CapitalParado>(
      `/analytics/${cid}/estoque/capital-parado${q({ periodo_ini: ini, periodo_fim: fim, base_velocidade: base, filial })}`,
    ),

  estoqueSimulador: (cid: number, ini: number, fim: number, objetivoDias = 60, base = 'fonte', filial?: string) =>
    api.get<SimuladorEstoque>(
      `/analytics/${cid}/estoque/simulador${q({ periodo_ini: ini, periodo_fim: fim, objetivo_dias: objetivoDias, base_velocidade: base, filial })}`,
    ),

  estoqueMatriz: (cid: number, ini: number, fim: number, base = 'fonte', filial?: string) =>
    api.get<MatrizEstoque>(
      `/analytics/${cid}/estoque/matriz${q({ periodo_ini: ini, periodo_fim: fim, base_velocidade: base, filial })}`,
    ),

  mercadoPerfil: (cid: number) =>
    api.get<PerfilMercado>(`/analytics/${cid}/mercado/perfil`),

  mercado: (cid: number, uf?: string, mercado?: string, molecula?: string) =>
    api.get<ResumoMercado>(`/analytics/${cid}/mercado${q({ uf, mercado, molecula })}`),

  mercadoShare: (cid: number, uf?: string, mercado?: string, molecula?: string, base = 'unidades') =>
    api.get<ShareIndustria>(`/analytics/${cid}/mercado/share${q({ uf, mercado, molecula, base })}`),

  mercadoShareCliente: (cid: number) =>
    api.get<ShareCliente>(`/analytics/${cid}/mercado/share-cliente`),

  mercadoRanking: (cid: number, uf?: string, topN = 30) =>
    api.get<RankingMercados>(`/analytics/${cid}/mercado/ranking${q({ uf, top_n: topN })}`),

  mercadoRegional: (cid: number, mercado?: string, molecula?: string, topN = 30) =>
    api.get<MercadoRegional>(`/analytics/${cid}/mercado/regional${q({ mercado, molecula, top_n: topN })}`),

  mercadoVsCliente: (cid: number, uf?: string, mercado?: string, molecula?: string) =>
    api.get<ClienteVsMercado>(`/analytics/${cid}/mercado/vs-cliente${q({ uf, mercado, molecula })}`),

  mercadoPonte: (cid: number, ini: number, fim: number, uf?: string, topN = 50) =>
    api.get<PonteMercado>(
      `/analytics/${cid}/mercado/ponte${q({ periodo_ini: ini, periodo_fim: fim, uf, top_n: topN })}`,
    ),

  precoComparabilidade: (cid: number) =>
    api.get<Comparabilidade>(`/analytics/${cid}/preco/comparabilidade`),

  preco: (cid: number, ini: number, fim: number, uf?: string, minimoUnidades = 200) =>
    api.get<PrecoVsConcorrentes>(
      `/analytics/${cid}/preco${q({ periodo_ini: ini, periodo_fim: fim, uf, minimo_unidades: minimoUnidades })}`,
    ),

  precoEvolucao: (cid: number, ini: number, fim: number, produtoId?: number, uf?: string) =>
    api.get<EvolucaoPreco>(
      `/analytics/${cid}/preco/evolucao${q({ periodo_ini: ini, periodo_fim: fim, produto_id: produtoId, uf })}`,
    ),

  precoVarejo: (cid: number, uf?: string, mercado?: string, molecula?: string, topN = 30) =>
    api.get<PrecoVarejo>(`/analytics/${cid}/preco/varejo${q({ uf, mercado, molecula, top_n: topN })}`),
}
