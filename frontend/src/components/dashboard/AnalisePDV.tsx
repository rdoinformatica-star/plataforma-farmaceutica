import { Th, useOrdenacao } from '../Tabela'
import { Aviso, Card, Carregando, Vazio } from '../ui'
import type { RankingPDVs } from '../../lib/analytics'
import { brl, inteiro, pct } from '../../lib/format'

const VISOES = [
  { valor: 'ranking', rotulo: 'Ranking' },
  { valor: 'novos', rotulo: 'Novos' },
  { valor: 'sumidos', rotulo: 'Sumidos' },
] as const

export function AnalisePDV({
  dados,
  visao,
  setVisao,
  carregando,
}: {
  dados: RankingPDVs | undefined
  visao: string
  setVisao: (v: string) => void
  carregando: boolean
}) {
  const { itens, ordem, alternar } = useOrdenacao(
    dados?.disponivel ? dados.itens : [],
  )

  if (!carregando && dados && !dados.disponivel) return null

  return (
    <Card
      titulo="Desempenho por PDV"
      acoes={
        <div className="linha" style={{ gap: 6 }}>
          {VISOES.map((v) => (
            <button key={v.valor} className={visao === v.valor ? 'primario' : ''}
                    onClick={() => setVisao(v.valor)}>
              {v.rotulo}
            </button>
          ))}
        </div>
      }
    >
      {carregando || !dados ? (
        <Carregando />
      ) : !dados.disponivel ? null : !dados.itens.length ? (
        <Vazio icone={null} titulo="Nenhum PDV nesta visão." />
      ) : dados.visao === 'ranking' ? (
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
                <Th campo="pdv" ordem={ordem} alternar={alternar}>PDV</Th>
                <Th campo="faturamento" ordem={ordem} alternar={alternar} num>Faturamento</Th>
                <Th campo="n_skus" ordem={ordem} alternar={alternar} num>SKUs</Th>
                <Th campo="participacao_pct" ordem={ordem} alternar={alternar} num>Participação</Th>
                <Th campo="variacao_pct" ordem={ordem} alternar={alternar} num>Variação</Th>
              </tr>
            </thead>
            <tbody>
              {itens.map((it) => (
                <tr key={it.pdv_id}>
                  <td>{it.pdv}</td>
                  <td className="num">{brl(it.faturamento)}</td>
                  <td className="num">{inteiro(it.n_skus)}</td>
                  <td className="num">{it.participacao_pct != null ? pct(it.participacao_pct) : '—'}</td>
                  <td className={`num ${it.variacao_pct == null ? '' : it.variacao_pct >= 0 ? 'pos' : 'neg'}`}>
                    {it.variacao_pct == null ? 'novo' : `${it.variacao_pct! >= 0 ? '+' : ''}${pct(it.variacao_pct)}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <>
          <div className="mut" style={{ fontSize: 12, marginBottom: 10 }}>
            {dados.total} PDV(s) {visao === 'novos' ? 'novos' : 'que sumiram'} — comparado ao
            período anterior de mesma duração.
          </div>
          <table>
            <tbody>
              {dados.itens.map((it) => (
                <tr key={it.pdv_id}><td>{it.pdv}</td></tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </Card>
  )
}
