import { Th, useOrdenacao } from '../Tabela'
import { SeletorUF } from './SeletorUF'
import { Aviso, Card, Carregando, Tag, Vazio } from '../ui'
import type { AnaliseUF, PotencialProdutos, RankingProdutos as TipoRanking } from '../../lib/analytics'
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
  ufs,
  uf,
  setUf,
  potencial,
}: {
  dados: TipoRanking | undefined
  ordenar: string
  setOrdenar: (o: string) => void
  limite: number
  setLimite: (n: number) => void
  carregando: boolean
  ufs?: AnaliseUF
  uf?: string
  setUf?: (uf: string | undefined) => void
  potencial?: PotencialProdutos
}) {
  const { itens, ordem, alternar } = useOrdenacao(
    dados?.disponivel ? dados.itens : [],
  )

  // Potencial e indice vem do cruzamento com o IQVIA — cálculo separado do
  // ranking, casado por produto_id. Só existe para SKUs cuja apresentação
  // casa exatamente com o mercado.
  const pot = new Map<number, { valor: number; indice: number | null }>()
  const soMolecula = new Set<number>()
  if (potencial?.disponivel) {
    for (const i of potencial.itens) pot.set(i.produto_id, { valor: i.potencial_valor, indice: i.indice })
    for (const i of potencial.contexto_molecula) soMolecula.add(i.produto_id)
  }
  const temPotencial = pot.size > 0

  return (
    <Card
      titulo="Ranking de produtos"
      acoes={
        <div className="linha" style={{ gap: 8, alignItems: 'flex-end' }}>
          {setUf && <SeletorUF ufs={ufs} valor={uf} aoMudar={setUf} />}
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
        <div className="pilha" style={{ gap: 8 }}>
          {dados.comparacao_valida === false && (
            <Aviso tipo="atencao">
              A coluna "Variação" não pôde ser calculada: o histórico disponível não
              cobre todo o período de comparação.
            </Aviso>
          )}
          <div className="rolagem">
          <table>
            <thead>
              <tr>
                <Th campo="produto" ordem={ordem} alternar={alternar}>Produto</Th>
                <Th campo="faturamento_atual" ordem={ordem} alternar={alternar} num>Faturamento</Th>
                <Th campo="unidades_atual" ordem={ordem} alternar={alternar} num>Unidades</Th>
                <Th campo="participacao_pct" ordem={ordem} alternar={alternar} num>Participação</Th>
                <Th campo="variacao_pct" ordem={ordem} alternar={alternar} num>Variação</Th>
                {temPotencial && (
                  <>
                    <th className="num" title="Penetração deste SKU no mercado IQVIA dividida pela penetração média da carteira × 100. Abaixo de 100 = sub-penetrado.">
                      Índice
                    </th>
                    <th className="num" title="Quanto o SKU venderia a mais se atingisse a penetração média da carteira no mercado dele. Só para SKUs com apresentação idêntica no IQVIA.">
                      Potencial
                    </th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {itens.map((it) => {
                const p = pot.get(it.produto_id)
                return (
                <tr key={it.produto_id}>
                  <td>{it.produto}</td>
                  <td className="num">{brl(it.faturamento_atual)}</td>
                  <td className="num">{inteiro(it.unidades_atual)}</td>
                  <td className="num">{it.participacao_pct != null ? pct(it.participacao_pct) : '—'}</td>
                  <td className={`num ${it.variacao_pct == null ? '' : it.variacao_pct >= 0 ? 'pos' : 'neg'}`}>
                    {it.variacao_pct == null ? 'novo' : `${it.variacao_pct >= 0 ? '+' : ''}${pct(it.variacao_pct)}`}
                  </td>
                  {temPotencial && (
                    <>
                      <td className="num">
                        {p?.indice != null ? (
                          <Tag tipo={p.indice >= 100 ? 't-ok' : p.indice >= 50 ? 't-hip' : 't-erro'}>
                            {Math.round(p.indice)}
                          </Tag>
                        ) : soMolecula.has(it.produto_id) ? (
                          <span className="mut" title="Só casou por molécula no IQVIA — base ampla demais para virar meta">
                            amplo
                          </span>
                        ) : '—'}
                      </td>
                      <td className="num">
                        {/* Zero aqui nao e "nada": e SKU ja no ritmo da
                            referencia ou acima. "R$ 0,00" leria como falha. */}
                        {!p ? '—' : p.valor > 0 ? brl(p.valor) : (
                          <span className="mut" title="Já está na penetração de referência ou acima dela">
                            no ritmo
                          </span>
                        )}
                      </td>
                    </>
                  )}
                </tr>
                )
              })}
            </tbody>
          </table>
          </div>
          {potencial?.disponivel && (
            <div className="mut" style={{ fontSize: 12 }}>
              Potencial total: <b>{brl(potencial.potencial_total)}</b> em{' '}
              {inteiro(potencial.n_skus)} SKUs, contra uma penetração de referência de{' '}
              {potencial.penetracao_referencia_pct.toFixed(2)}% do mercado.{' '}
              {potencial.n_so_molecula > 0 && (
                <>
                  {inteiro(potencial.n_so_molecula)} SKU(s) só casaram por molécula no
                  IQVIA e ficam marcados como "amplo", fora do total — comparar um SKU
                  com o mercado da molécula inteira daria um número falso.{' '}
                </>
              )}
              Os potenciais <b>não se somam</b>: SKUs da mesma molécula competem entre si.
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
