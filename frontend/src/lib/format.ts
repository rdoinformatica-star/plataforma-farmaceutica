const BRL = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  maximumFractionDigits: 2,
})
const INT = new Intl.NumberFormat('pt-BR')

export const brl = (v: number | null | undefined) => (v == null ? '—' : BRL.format(v))
export const inteiro = (v: number | null | undefined) => (v == null ? '—' : INT.format(v))

export function numero(v: number | null | undefined, casas = 1) {
  if (v == null || !Number.isFinite(v)) return '—'
  return v.toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas })
}

export function pct(v: number | null | undefined, casas = 1) {
  if (v == null || !Number.isFinite(v)) return '—'
  return `${numero(v, casas)}%`
}

export function bytes(v: number | null | undefined) {
  if (v == null) return '—'
  if (v < 1024) return `${v} B`
  if (v < 1024 * 1024) return `${numero(v / 1024, 0)} KB`
  return `${numero(v / (1024 * 1024), 1)} MB`
}

export function duracao(seg: number | null | undefined) {
  if (seg == null) return '—'
  if (seg < 60) return `${numero(seg, 1)}s`
  const m = Math.floor(seg / 60)
  const s = Math.round(seg % 60)
  return `${m}min ${s}s`
}

export function dataHora(iso: string | null | undefined) {
  if (!iso) return '—'
  const d = new Date(iso.includes('T') ? iso : iso.replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** 202607 -> 07/2026 */
export function periodo(p: number | string | null | undefined) {
  if (p == null) return '—'
  const s = String(p)
  if (/^\d{6}$/.test(s)) return `${s.slice(4)}/${s.slice(0, 4)}`
  return s
}

export function faixaPeriodo(min: unknown, max: unknown) {
  if (min == null && max == null) return null
  if (min === max) return periodo(min as number)
  return `${periodo(min as number)} a ${periodo(max as number)}`
}

const NOMES_PAPEL: Record<string, string> = {
  PRODUTO: 'Produto',
  PDV: 'Ponto de venda',
  DISTRIBUIDOR: 'Distribuidor',
  MARCA: 'Marca',
  UF: 'Estado',
  CIDADE: 'Cidade',
  PERIODO: 'Período',
  DATA: 'Data',
  VALOR: 'Valor em R$',
  UNIDADE: 'Unidades',
  CODIGO_EAN: 'Código de barras',
  CNPJ: 'CNPJ',
  CATEGORIA: 'Categoria',
  CODIGO: 'Código',
  CHAVE: 'Chave',
  DESCONHECIDO: 'Não identificado',
}
export const nomePapel = (p: string) => NOMES_PAPEL[p] ?? p

const NOMES_ELO: Record<string, string> = {
  DISTRIBUIDOR_PDV: 'Distribuidor → PDV',
  PDV_CONSUMIDOR: 'PDV → consumidor',
  INDUSTRIA_DISTRIBUIDOR: 'Indústria → distribuidor',
  ESTOQUE: 'Posição de estoque',
  CADASTRAL: 'Cadastro',
  INDEFINIDO: 'Não definido',
}
export const nomeElo = (e: string) => NOMES_ELO[e] ?? e

const NOMES_PROBLEMA: Record<string, string> = {
  OUTLIER: 'Valores fora do padrão',
  ESPACOS_SOBRANDO: 'Espaços sobrando',
  VARIANTES_DE_CAIXA: 'Escrito de mais de um jeito',
  NUMERO_COMO_TEXTO: 'Número guardado como texto',
  CODIGO_INVALIDO: 'Código inválido',
}
export const nomeProblema = (t: string) => NOMES_PROBLEMA[t] ?? t
