import { Card, Carregando } from '../ui'
import type { Concentracao as TipoConcentracao } from '../../lib/analytics'
import { brl, pct } from '../../lib/format'

export function Concentracao({
  dados,
  contexto,
  setContexto,
  carregando,
}: {
  dados: TipoConcentracao | undefined
  contexto: string
  setContexto: (c: string) => void
  carregando: boolean
}) {
  return (
    <Card
      titulo="Concentração"
      acoes={
        <div className="linha" style={{ gap: 6 }}>
          <button className={contexto === 'produtos' ? 'primario' : ''} onClick={() => setContexto('produtos')}>
            Produtos
          </button>
          <button className={contexto === 'pdvs' ? 'primario' : ''} onClick={() => setContexto('pdvs')}>
            PDVs
          </button>
        </div>
      }
    >
      {carregando || !dados ? (
        <Carregando />
      ) : !dados.disponivel ? (
        <div className="mut">{dados.motivo}</div>
      ) : (
        <div className="pilha" style={{ gap: 10 }}>
          {dados.faixas.map((fx) => (
            <div key={fx.top}>
              <div className="linha entre" style={{ marginBottom: 4 }}>
                <span style={{ fontSize: 13 }}>Top {fx.top} {contexto}</span>
                <span className="num" style={{ fontWeight: 600 }}>
                  {fx.percentual != null ? pct(fx.percentual) : '—'}
                </span>
              </div>
              <div className="barra"><div style={{ width: `${Math.min(fx.percentual ?? 0, 100)}%` }} /></div>
            </div>
          ))}
          <div className="mut" style={{ fontSize: 11.5, marginTop: 4 }}>
            {dados.n_total_elementos} {contexto} no total · faturamento do período: {brl(dados.faturamento_total)}
          </div>
        </div>
      )}
    </Card>
  )
}
