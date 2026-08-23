import { Th, useOrdenacao } from '../Tabela'
import { SeletorUF } from './SeletorUF'
import { Aviso, Card, Carregando, Vazio } from '../ui'
import type { AnaliseUF, PotencialPDVs, RankingPDVs } from '../../lib/analytics'
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
  ufs,
  uf,
  setUf,
  potencial,
}: {
  dados: RankingPDVs | undefined
  visao: string
  setVisao: (v: string) => void
  carregando: boolean
  ufs?: AnaliseUF
  uf?: string
  setUf?: (uf: string | undefined) => void
  potencial?: PotencialPDVs
}) {
  const { itens, ordem, alternar } = useOrdenacao(
    dados?.disponivel ? dados.itens : [],
  )

  if (!carregando && dados && !dados.disponivel) return null

  // Potencial vem de um cálculo separado (base de comparação diferente do
  // ranking): indexa por PDV para casar linha a linha sem refazer a conta.
  const potPorPdv = new Map<number, number>()
  if (potencial?.disponivel) {
    for (const i of potencial.itens) potPorPdv.set(i.pdv_id, i.potencial_valor)
  }
  const temPotencial = potPorPdv.size > 0
  const ehRanking = dados?.disponivel && dados.visao === 'ranking'

  return (
    <Card
      titulo="Desempenho por PDV"
      acoes={
        <div className="linha" style={{ gap: 10, alignItems: 'flex-end' }}>
          {setUf && <SeletorUF ufs={ufs} valor={uf} aoMudar={setUf} />}
          <div className="linha" style={{ gap: 6 }}>
            {VISOES.map((v) => (
              <button key={v.valor} className={visao === v.valor ? 'primario' : ''}
                      onClick={() => setVisao(v.valor)}>
                {v.rotulo}
              </button>
            ))}
          </div>
        </div>
      }
    >
      {carregando || !dados ? (
        <Carregando />
      ) : !dados.disponivel ? null : !dados.itens.length ? (
        <Vazio icone={null} titulo="Nenhum PDV nesta visão." />
      ) : (
        <div className="pilha" style={{ gap: 8 }}>
          {!ehRanking && (
            <div className="mut" style={{ fontSize: 12 }}>
              {inteiro(dados.total)} PDV(s) {visao === 'novos' ? 'novos' : 'que sumiram'} —
              comparado ao período anterior de mesma duração
              {dados.faturamento_total != null && (
                <>
                  {' · '}
                  <b>{brl(dados.faturamento_total)}</b>{' '}
                  {visao === 'novos' ? 'ganhos' : 'que deixaram de entrar'}
                </>
              )}
              {uf ? ` · só ${uf}` : ''}.
            </div>
          )}
          {ehRanking && dados.comparacao_valida === false && (
            <Aviso tipo="atencao">
              A coluna "Variação" não pôde ser calculada: o histórico disponível não
              cobre todo o período de comparação.
            </Aviso>
          )}
          {!ehRanking && (
            <Aviso tipo="info">
              O faturamento aqui é o do período em que estes PDVs têm venda
              {visao === 'novos' ? ' (o atual)' : ' (o anterior)'} — a única janela em
              que eles existem. Por isso não há variação: falta a outra ponta da
              comparação.
            </Aviso>
          )}
          <div className="rolagem">
            <table>
              <thead>
                <tr>
                  <Th campo="pdv" ordem={ordem} alternar={alternar}>PDV</Th>
                  <Th campo="faturamento" ordem={ordem} alternar={alternar} num>Faturamento</Th>
                  <Th campo="n_skus" ordem={ordem} alternar={alternar} num>SKUs</Th>
                  <Th campo="participacao_pct" ordem={ordem} alternar={alternar} num>Participação</Th>
                  {ehRanking && (
                    <Th campo="variacao_pct" ordem={ordem} alternar={alternar} num>Variação</Th>
                  )}
                  {ehRanking && temPotencial && (
                    <th
                      className="num"
                      title="Quanto este PDV compraria a mais se chegasse ao mix mediano da faixa acima, ao R$/SKU típico dela. Referência interna — o IQVIA não tem grão de PDV."
                    >
                      Potencial
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {itens.map((it) => (
                  <tr key={it.pdv_id}>
                    <td>{it.pdv}</td>
                    <td className="num">{it.faturamento != null ? brl(it.faturamento) : '—'}</td>
                    <td className="num">{it.n_skus != null ? inteiro(it.n_skus) : '—'}</td>
                    <td className="num">{it.participacao_pct != null ? pct(it.participacao_pct) : '—'}</td>
                    {ehRanking && (
                      <td className={`num ${it.variacao_pct == null ? '' : it.variacao_pct >= 0 ? 'pos' : 'neg'}`}>
                        {it.variacao_pct == null ? 'novo' : `${it.variacao_pct >= 0 ? '+' : ''}${pct(it.variacao_pct)}`}
                      </td>
                    )}
                    {ehRanking && temPotencial && (
                      <td className="num">
                        {potPorPdv.has(it.pdv_id) ? brl(potPorPdv.get(it.pdv_id)!) : '—'}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {ehRanking && potencial?.disponivel && (
            <div className="mut" style={{ fontSize: 12 }}>
              Potencial total da carteira: <b>{brl(potencial.potencial_total)}</b> em{' '}
              {inteiro(potencial.n_pdvs_com_potencial)} PDVs.{' '}
              {inteiro(potencial.n_pdvs_sem_referencia)} já estão na faixa de mix mais
              alta e ficam sem potencial — não há referência observada acima deles.
              Os valores <b>não se somam como meta</b>: assumem que cada PDV sobe um
              degrau de mix mantendo o R$/SKU típico.
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
