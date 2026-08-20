import { useState } from 'react'

import { ComoFoiCalculado } from '../ComoFoiCalculado'
import { Card, Kpi } from '../ui'
import type { Comparacao, Resumo } from '../../lib/analytics'
import { brl, inteiro, pct } from '../../lib/format'

function Variacao({ pctv, valido }: { pctv: number | null; valido: boolean }) {
  if (!valido) return <span className="mut" title="Não há dados suficientes para comparar este período">sem histórico</span>
  if (pctv == null) return <span className="mut">novo</span>
  const tom = pctv >= 0 ? 'pos' : 'neg'
  const sinal = pctv >= 0 ? '+' : ''
  return <span className={tom}>{sinal}{pct(pctv)}</span>
}

export function ResumoExecutivo({ resumo }: { resumo: Resumo }) {
  const [modo, setModo] = useState<'anterior' | 'ano_anterior'>('ano_anterior')

  if (!resumo.disponivel) return null

  const cmp: Comparacao | null =
    modo === 'ano_anterior' && resumo.comparacao_ano_anterior
      ? resumo.comparacao_ano_anterior
      : resumo.comparacao_periodo_anterior

  return (
    <Card
      titulo="Resumo executivo"
      acoes={
        <div className="linha" style={{ gap: 6 }}>
          {resumo.comparacao_ano_anterior && (
            <button
              className={modo === 'ano_anterior' ? 'primario' : ''}
              onClick={() => setModo('ano_anterior')}
            >
              YoY
            </button>
          )}
          <button
            className={modo === 'anterior' ? 'primario' : ''}
            onClick={() => setModo('anterior')}
          >
            Período anterior
          </button>
          <ComoFoiCalculado
            calculo={{
              titulo: 'Como o resumo foi calculado',
              formula: cmp.calculo.formula,
              periodo: resumo.periodo.label,
              valores: Object.entries(cmp.calculo.valores ?? {}).map(([rotulo, valor]) => ({
                rotulo, valor: String(valor),
              })),
              premissas: cmp.calculo.premissas,
            }}
          />
        </div>
      }
    >
      <div className="kpis">
        <Kpi rotulo="Faturamento" valor={brl(resumo.faturamento)}
             sub={<Variacao pctv={cmp.faturamento_variacao_pct} valido={cmp.comparacao_valida} />} />
        <Kpi rotulo="Unidades" valor={inteiro(resumo.unidades)}
             sub={<Variacao pctv={cmp.unidades_variacao_pct} valido={cmp.comparacao_valida} />} />
        <Kpi rotulo="Produtos ativos" valor={inteiro(resumo.n_produtos)} />
        <Kpi rotulo="Pontos de venda" valor={inteiro(resumo.n_pdvs)} />
      </div>
      {!cmp.comparacao_valida && (
        <div className="mut" style={{ fontSize: 12, marginTop: 10 }}>
          Sem dado suficiente para comparar {cmp.periodo_atual.label} com{' '}
          {cmp.periodo_anterior.label} — o histórico não cobre todo o período de
          comparação. Veja o motivo em "Ver como foi calculado".
        </div>
      )}
      <div className="mut" style={{ fontSize: 12, marginTop: 10 }}>
        Comparando {cmp.periodo_atual.label} com {cmp.periodo_anterior.label}
        {' — '}{cmp.rotulo}.
      </div>
    </Card>
  )
}
