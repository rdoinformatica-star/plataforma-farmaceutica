import { useState } from 'react'

import { Grafico, useCoresGrafico } from '../Grafico'
import { Card, Carregando } from '../ui'
import type { EvolucaoMensal as TipoEvolucao } from '../../lib/analytics'

const METRICAS = [
  { valor: 'faturamento', rotulo: 'Faturamento' },
  { valor: 'unidades', rotulo: 'Unidades' },
  { valor: 'pdvs', rotulo: 'PDVs' },
  { valor: 'skus', rotulo: 'SKUs' },
] as const

export function EvolucaoMensal({
  dados,
  metrica,
  setMetrica,
  carregando,
}: {
  dados: TipoEvolucao | undefined
  metrica: string
  setMetrica: (m: string) => void
  carregando: boolean
}) {
  const [tipo, setTipo] = useState<'linha' | 'barra'>('linha')
  const cor = useCoresGrafico()

  return (
    <Card
      titulo="Evolução mensal"
      acoes={
        <div className="linha" style={{ gap: 6 }}>
          {METRICAS.map((m) => (
            <button
              key={m.valor}
              className={metrica === m.valor ? 'primario' : ''}
              onClick={() => setMetrica(m.valor)}
            >
              {m.rotulo}
            </button>
          ))}
          <button className="discreto" onClick={() => setTipo(tipo === 'linha' ? 'barra' : 'linha')}>
            {tipo === 'linha' ? 'ver em barras' : 'ver em linha'}
          </button>
        </div>
      }
    >
      {carregando || !dados ? (
        <Carregando />
      ) : !dados.disponivel ? (
        <div className="mut">{dados.motivo}</div>
      ) : (
        <Grafico
          opcoes={{
            xAxis: { type: 'category', data: dados.serie.map((s) => s.label),
                     axisLine: { lineStyle: { color: cor.borderForte } },
                     axisLabel: { color: cor.muted } },
            yAxis: { type: 'value', splitLine: { lineStyle: { color: cor.border } },
                     axisLabel: { color: cor.muted } },
            series: [{
              type: tipo === 'linha' ? 'line' : 'bar',
              data: dados.serie.map((s) => s.valor),
              smooth: tipo === 'linha',
              areaStyle: tipo === 'linha' ? { opacity: 0.08, color: cor.wine } : undefined,
              itemStyle: { color: cor.wine },
              lineStyle: { color: cor.wine, width: 2 },
            }],
          }}
        />
      )}
    </Card>
  )
}
