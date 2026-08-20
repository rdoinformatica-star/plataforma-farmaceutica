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
}
