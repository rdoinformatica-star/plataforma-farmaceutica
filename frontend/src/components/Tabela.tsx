/** Ordenacao de tabela: um hook + um <Th> que se comporta como botao.
 *
 * Ordena no cliente, sobre a lista que ja veio da API. Isso e proposital:
 * as respostas do backend sao limitadas (top_n / limite), entao ordenar aqui
 * reordena o RECORTE que esta na tela, nao a base inteira. O <Th> mostra a
 * direcao ativa para nao dar a impressao de que a tabela foi recalculada.
 *
 * Texto ordena com localeCompare pt-BR (acento e caixa ficam certos);
 * numero ordena numericamente. null/undefined vao sempre para o fim, nos dois
 * sentidos — um vazio nao e "o menor", e ausencia de dado.
 */
import { useMemo, useState } from 'react'

export type Direcao = 'asc' | 'desc'

export interface Ordenacao<T> {
  campo: keyof T & string
  direcao: Direcao
}

function compara(a: unknown, b: unknown): number {
  const aVazio = a === null || a === undefined || a === ''
  const bVazio = b === null || b === undefined || b === ''
  if (aVazio && bVazio) return 0
  if (aVazio) return 1
  if (bVazio) return -1
  if (typeof a === 'number' && typeof b === 'number') return a - b
  if (typeof a === 'boolean' && typeof b === 'boolean') return Number(a) - Number(b)
  return String(a).localeCompare(String(b), 'pt-BR', { numeric: true, sensitivity: 'base' })
}

/** Devolve a lista ordenada e os controles para o <Th>.
 *  `T extends object` (não `Record<string, unknown>`) de propósito: as
 *  respostas da API são interfaces concretas sem index signature, e exigir
 *  uma teria forçado todo call site a alargar o tipo à toa. O acesso ao
 *  campo em si é feito por chave dinâmica dentro do hook, então o `unknown`
 *  fica contido aqui — nunca vaza para quem usa `useOrdenacao`. */
export function useOrdenacao<T extends object>(
  itens: T[] | undefined,
  inicial?: Ordenacao<T>,
) {
  const [ordem, setOrdem] = useState<Ordenacao<T> | null>(inicial ?? null)

  const ordenados = useMemo(() => {
    if (!itens) return []
    if (!ordem) return itens
    const copia = [...itens]
    copia.sort((x, y) => {
      const r = compara(
        (x as Record<string, unknown>)[ordem.campo],
        (y as Record<string, unknown>)[ordem.campo],
      )
      return ordem.direcao === 'asc' ? r : -r
    })
    return copia
  }, [itens, ordem])

  /** Primeiro clique: ascendente para texto, descendente para numero
   *  (numa coluna de valor o util quase sempre e "os maiores primeiro").
   *  Clique seguinte inverte. Terceiro clique volta a ordem original. */
  function alternar(campo: keyof T & string, tipo: 'texto' | 'numero' = 'texto') {
    setOrdem((atual) => {
      if (!atual || atual.campo !== campo) {
        return { campo, direcao: tipo === 'numero' ? 'desc' : 'asc' }
      }
      const primeira: Direcao = tipo === 'numero' ? 'desc' : 'asc'
      if (atual.direcao === primeira) {
        return { campo, direcao: primeira === 'asc' ? 'desc' : 'asc' }
      }
      return null
    })
  }

  return { itens: ordenados, ordem, alternar }
}

/** Cabecalho clicavel. `campo` liga a coluna ao dado; `num` alinha a direita
 *  e faz o primeiro clique ser decrescente. */
export function Th<T extends object>({
  campo,
  ordem,
  alternar,
  num,
  titulo,
  children,
}: {
  campo?: keyof T & string
  ordem?: Ordenacao<T> | null
  alternar?: (campo: keyof T & string, tipo?: 'texto' | 'numero') => void
  num?: boolean
  titulo?: string
  children?: React.ReactNode
}) {
  if (!campo || !alternar) {
    return <th className={num ? 'num' : undefined}>{children}</th>
  }
  const ativa = ordem?.campo === campo
  const seta = !ativa ? '↕' : ordem!.direcao === 'asc' ? '↑' : '↓'
  return (
    <th className={`ordenavel${num ? ' num' : ''}${ativa ? ' ativa' : ''}`}>
      <button
        type="button"
        onClick={() => alternar(campo, num ? 'numero' : 'texto')}
        title={titulo ?? `Ordenar por ${String(children)}`}
        aria-label={`Ordenar por ${String(children)}`}
      >
        <span>{children}</span>
        <i aria-hidden="true">{seta}</i>
      </button>
    </th>
  )
}
