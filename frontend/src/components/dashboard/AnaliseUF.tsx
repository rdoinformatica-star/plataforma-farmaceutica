import { Th, useOrdenacao } from '../Tabela'
import { Aviso, Card, Carregando, Vazio } from '../ui'
import type { AnaliseUF as TipoUF } from '../../lib/analytics'
import { brl, inteiro, pct } from '../../lib/format'

export function AnaliseUF({ dados, carregando }: { dados: TipoUF | undefined; carregando: boolean }) {
  const { itens, ordem, alternar } = useOrdenacao(
    dados?.disponivel ? dados.itens : [],
  )

  if (!carregando && dados && !dados.disponivel) return null // sem UF nos dados: nem mostra o modulo

  return (
    <Card titulo="Desempenho por estado">
      {carregando || !dados ? (
        <Carregando />
      ) : !dados.disponivel ? null : !dados.itens.length ? (
        <Vazio icone={null} titulo="Nenhuma UF com venda neste período." />
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
                <Th campo="uf" ordem={ordem} alternar={alternar}>UF</Th>
                <Th campo="faturamento" ordem={ordem} alternar={alternar} num>Faturamento</Th>
                <Th campo="unidades" ordem={ordem} alternar={alternar} num>Unidades</Th>
                <Th campo="participacao_pct" ordem={ordem} alternar={alternar} num>Participação</Th>
                <Th campo="variacao_pct" ordem={ordem} alternar={alternar} num>Variação</Th>
              </tr>
            </thead>
            <tbody>
              {itens.map((it) => (
                <tr key={it.uf}>
                  <td style={{ fontWeight: 600 }}>{it.uf}</td>
                  <td className="num">{brl(it.faturamento)}</td>
                  <td className="num">{inteiro(it.unidades)}</td>
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
