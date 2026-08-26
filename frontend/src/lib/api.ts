export interface ErroApi {
  codigo: string
  mensagem: string
  detalhe?: string | null
  [k: string]: unknown
}

export class FalhaApi extends Error {
  status: number
  erro: ErroApi
  constructor(status: number, erro: ErroApi) {
    super(erro.mensagem)
    this.status = status
    this.erro = erro
  }
}

async function req<T>(rota: string, init?: RequestInit): Promise<T> {
  const baseUrl = import.meta.env.DEV
    ? '/api'
    : 'https://plataforma-farmaceutica-production.up.railway.app/api'
  const r = await fetch(`${baseUrl}${rota}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  const texto = await r.text()
  const corpo = texto ? JSON.parse(texto) : null
  if (!r.ok) {
    const erro: ErroApi = corpo?.erro ?? {
      codigo: 'ERRO',
      mensagem: corpo?.detail ? String(corpo.detail) : `Falha ${r.status}`,
    }
    throw new FalhaApi(r.status, erro)
  }
  return corpo as T
}

export const api = {
  get: <T,>(rota: string) => req<T>(rota),
  post: <T,>(rota: string, corpo?: unknown) =>
    req<T>(rota, { method: 'POST', body: corpo ? JSON.stringify(corpo) : undefined }),
  put: <T,>(rota: string, corpo?: unknown) =>
    req<T>(rota, { method: 'PUT', body: corpo ? JSON.stringify(corpo) : undefined }),
  del: <T,>(rota: string) => req<T>(rota, { method: 'DELETE' }),
  upload: async (arquivo: File) => {
    const fd = new FormData()
    fd.append('arquivo', arquivo)
    const r = await fetch('/api/arquivos/upload', { method: 'POST', body: fd })
    const corpo = await r.json()
    if (!r.ok) throw new FalhaApi(r.status, corpo.erro)
    return corpo as { sha256: string; nome: string; bytes: number; caminho: string }
  },
}

/* ───────────────────────────── tipos ───────────────────────────── */

export interface Cliente {
  id: number
  nome: string
  cnpj: string | null
  uf_principal: string | null
  grupo: string | null
  observacoes: string | null
  ativo: number
  n_importacoes: number
  ultima_importacao: string | null
  criado_em: string
}

export interface Fonte {
  id: number
  codigo: string
  nome: string
  descricao: string
  natureza_elo: string
  granularidade: string | null
  n_importacoes: number
  aviso_elo: string
}

export interface ItemDisco {
  nome: string
  caminho: string
  tipo: 'pasta' | 'arquivo'
  bytes: number | null
  modificado_em: string
  ext: string
  suportado: boolean
}

export interface Candidato {
  adaptador: string
  rotulo: string
  data_source: string
  data_source_id: number
  confianca: number
  motivo: string
  params_sugeridos: Record<string, unknown>
}

export interface Deteccao {
  arquivo: { nome: string; caminho: string; bytes: number; sha256: string }
  candidatos: Candidato[]
  previa: { colunas: string[]; linhas: Record<string, unknown>[] } | null
  ja_importado: { id: number; concluido_em: string; linhas_gravadas: number } | null
}

export interface Importacao {
  id: number
  arquivo_nome: string
  arquivo_bytes: number
  adaptador: string
  status: string
  progresso: number
  etapa_atual: string | null
  linhas_lidas: number
  linhas_gravadas: number
  linhas_descartadas: number
  motivo_descarte: string | null
  vigente: number
  substituido_por: number | null
  duracao_seg: number | null
  pico_memoria_mb: number | null
  periodo_min: number | null
  periodo_max: number | null
  erro_mensagem: string | null
  erro_detalhe?: string | null
  iniciado_em: string
  concluido_em: string | null
  origem: string
  adaptador_forcado: number
  fonte: string
  fonte_nome: string
  natureza_elo: string
  cliente: string | null
  client_id: number | null
  em_andamento?: boolean
  eta_seg?: number | null
  posicao_na_fila?: number
  tem_perfil?: boolean
  colunas_pendentes?: number
  log?: { ts: string; nivel: string; texto: string }[]
  params?: Record<string, unknown>
}

export interface Papel {
  valor: string
  confianca: number
  evidencia: string
  alternativas: { valor: string; confianca: number }[]
}

export interface ColunaPerfil {
  ordem: number
  nome: string
  tipo_inferido: string
  tipo_bruto: string
  n_nulos: number
  pct_nulos: number
  n_distintos: number
  cardinalidade: number
  papel: Papel
  numerico: Record<string, number | boolean | { de: number; ate: number; n: number }[]>
  texto: Record<string, number | string>
  top: { v: string; n: number; pct: number }[]
  exemplos: string[]
  problemas: { tipo: string; n: number; detalhe: string }[]
}

export interface Perfil {
  versao: string
  dataset: {
    fonte: string
    linhas_lidas: number
    linhas_validas: number
    linhas_descartadas: number
    motivo_descarte: string | null
    amostras_descartadas: Record<string, unknown>[]
    colunas: number
    bytes: number
    duracao_ms: number
    base_estatistica: string
    periodo: { min: number | string | null; max: number | string | null; granularidade: string | null }
    entidades: Record<string, number>
    avisos: string[]
  }
  colunas: ColunaPerfil[]
  chaves_candidatas: { colunas: string[]; unica: boolean; n_duplicatas: number; base: string }[]
  duplicatas: { linhas_integrais: number; base?: string }
  limitacoes: string[]
  importacao: Importacao
}

export interface ColunaImport {
  id: number
  import_id: number
  ordem: number
  nome_original: string
  tipo_detectado: string
  papel_semantico: string
  papel_confianca: number
  papel_evidencia: string
  eh_nova: number
  decisao: string
  mapeado_para: string | null
  arquivo_nome?: string
  fonte?: string
  stats: Record<string, unknown>
}

export interface Estatisticas {
  clientes: number
  importacoes: number
  produtos: number
  produtos_novos: number
  pdvs: number
  distribuidores: number
  linhas_vendas: number
  linhas_estoque: number
  linhas_mercado: number
  colunas_pendentes: number
  mapeamentos_pendentes: number
  por_fonte: { codigo: string; nome: string; n_importacoes: number; linhas: number }[]
  ultima_importacao: {
    id: number
    arquivo_nome: string
    status: string
    concluido_em: string
    linhas_gravadas: number
    fonte: string
    cliente: string | null
  } | null
}

export interface Saude {
  ok: boolean
  versao: string
  etapa: number
  python: string
  sqlite: string
  db_path: string
  db_tamanho_mb: number
  tabelas: string[]
  n_tabelas: number
  fontes: number
  engine_ok: boolean
  engine_msg: string
  ia: {
    codigo: string
    rotulo: string
    disponivel: boolean
    exige_rede: boolean
    exige_chave: boolean
    observacao: string
  }[]
}
