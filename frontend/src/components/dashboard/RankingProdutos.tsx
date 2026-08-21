import { Th, useOrdenacao } from '../Tabela'
import { Aviso, Card, Carregando, Vazio } from '../ui'
import type { RankingProdutos as TipoRanking } from '../../lib/analytics'
import { brl, inteiro, pct } from '../../lib/format'

const ORDENACOES = [
  { valor: 'faturamento', rotulo: 'Maior faturamento' },
  { valor: 'unidades', rotulo: 'Maior unidades' },
  { valor: 'crescimento', rotulo: 'Maior crescimento' },
  { valor: 'queda', rotulo: 'Maior queda' },
] as const

const LIMITES = [10, 20, 50] as const

export function RankingProdutos({
  dados,
  ordenar,
  setOrdenar,
  limite,
  setLimite,
  carregando,
}: {
  dados: TipoRanking | undefined
  ordenar: string
  setOrdenar: (o: string) => void
  limite: number
  setLimite: (n: number) => void
  carregando: boolean
}) {
  const { itens, ordem, alternar } = useOrdenacao(
    dados?.disponivel ? dados.itens : [],
  )

  return (
    <Card
      titulo="Ranking de produtos"
      acoes={
        <div className="linha" style={{ gap: 6 }}>
          <select value={ordenar} onChange={(e) => setOrdenar(e.target.value)} style={{ width: 170 }}>
            {ORDENACOES.map((o) => (
              <option key={o.valor} value={o.valor}>{o.rotulo}</option>
            ))}
          </select>
          <select value={limite} onChange={(e) => setLimite(Number(e.target.value))} style={{ width: 90 }}>
            {LIMITES.map((n) => (
              <option key={n} value={n}>Top {n}</option>
            ))}
          </select>
        </div>
      }
    >
      {carregando || !dados ? (
        <Carregando />
      ) : !dados.disponivel ? (
        <Vazio icone={null} titulo={dados.motivo} />
      ) : !dados.itens.length ? (
        <Vazio icone={null} titulo="Nenhum produto vendido neste período." />
      ) : (
        <div className="rolagem">
          {dados.comparacao_valida === false && (
            <Aviso tipo="atencao">
              A coluna "Variação" não pôde ser calculada: o histórico disponível não
              cobre todo o período de comparação.
            </Aviso>
          )}
          <table>
            <thead>
              <tr>
                <Th campo="produto" ordem={ordem} alternar={alternar}>Produto</Th>
                <Th campo="faturamento_atual" ordem={ordem} alternar={alternar} num>Faturamento</Th>
                <Th campo="unidades_atual" ordem={ordem} alternar={alternar} num>Unidades</Th>
                <Th campo="participacao_pct" ordem={ordem} alternar={alternar} num>Participação</Th>
                <Th campo="variacao_pct" ordem={ordem} alternar={alternar} num>Variação</Th>
              </tr>
            </thead>
            <tbody>
              {itens.map((it) => (
                <tr key={it.produto_id}>
                  <td>{it.produto}</td>
                  <td className="num">{brl(it.faturamento_atual)}</td>
                  <td className="num">{inteiro(it.unidades_atual)}</td>
                  <td className="num">{it.participacao_pct != null ? pct(it.participacao_pct) : '—'}</td>
                  <td className={`num ${it.variacao_pct == null ? '' : it.variacao_pct >= 0 ? 'pos' : 'neg'}`}>
                    {it.variacao_pct == null ? 'novo' : `${it.variacao_pct >= 0 ? '+' : ''}${pct(it.variacao_pct)}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
