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
      comparacao_valida?: boolean
      itens: ItemPDV[]
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
      itens: ItemOportunidade[]
      pesos?: { potencial: number; impacto: number; facilidade: number }
      calculo: Calculo
    }

export type AlertasExpandidos = Indisponivel | { disponivel: true; itens: Alerta[]; n_total: number; calculo: Calculo }

const q = (params: Record<string, string | number | undefined>) =>
  '?' +
  Object.entries(params)
    .filter(([, v]) => v !== undefined)
    .map(([k, v]) => `${k}=${encodeURIComponent(v!)}`)
    .join('&')

export const analytics = {
  disponibilidade: (cid: number) => api.get<Disponibilidade>(`/analytics/${cid}/disponibilidade`),

  resumo: (cid: number, ini: number, fim: number) =>
    api.get<Resumo>(`/analytics/${cid}/resumo${q({ periodo_ini: ini, periodo_fim: fim })}`),

  evolucaoMensal: (cid: number, ini: number, fim: number, metrica: string) =>
    api.get<EvolucaoMensal>(
      `/analytics/${cid}/evolucao-mensal${q({ periodo_ini: ini, periodo_fim: fim, metrica })}`,
    ),

  produtos: (cid: number, ini: number, fim: number, ordenar: string, limite = 20, offset = 0) =>
    api.get<RankingProdutos>(
      `/analytics/${cid}/produtos${q({ periodo_ini: ini, periodo_fim: fim, ordenar, limite, offset })}`,
    ),

  produtosVariacao: (cid: number, ini: number, fim: number, direcao: 'crescimento' | 'queda') =>
    api.get<VariacaoProdutos>(
      `/analytics/${cid}/produtos/variacao${q({ periodo_ini: ini, periodo_fim: fim, direcao })}`,
    ),

  uf: (cid: number, ini: number, fim: number) =>
    api.get<AnaliseUF>(`/analytics/${cid}/uf${q({ periodo_ini: ini, periodo_fim: fim })}`),

  pdvs: (cid: number, ini: number, fim: number, visao: 'ranking' | 'novos' | 'sumidos', limite = 20) =>
    api.get<RankingPDVs>(
      `/analytics/${cid}/pdvs${q({ periodo_ini: ini, periodo_fim: fim, visao, limite })}`,
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
  ) =>
    api.get<MatrizOportunidades>(
      `/analytics/${cid}/oportunidades${q({
        periodo_ini: ini,
        periodo_fim: fim,
        peso_potencial: pesoPotencial,
        peso_impacto: pesoImpacto,
        peso_facilidade: pesoFacilidade,
      })}`,
    ),

  alertasExpandidos: (cid: number, ini: number, fim: number) =>
    api.get<AlertasExpandidos>(
      `/analytics/${cid}/alertas-expandidos${q({ periodo_ini: ini, periodo_fim: fim })}`,
    ),
}
