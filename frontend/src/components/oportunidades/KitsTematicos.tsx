import { ComoFoiCalculado } from '../ComoFoiCalculado'
import { Grafico, useCoresGrafico } from '../Grafico'
import { Aviso, Card, Vazio } from '../ui'
import type { Kit, Kits } from '../../lib/analytics'
import { brl } from '../../lib/format'

function GraficoSazonalidade({ kit }: { kit: Kit }) {
  const cor = useCoresGrafico()
  const picos = new Set(kit.picos_mes)
  return (
    <Grafico
      altura={140}
      opcoes={{
        grid: { left: 40, right: 8, top: 8, bottom: 20 },
        tooltip: { trigger: 'axis', valueFormatter: (v: unknown) => brl(Number(v)) },
        xAxis: {
          type: 'category',
          data: kit.distribuicao_por_mes.map((m) => m.mes_nome),
          axisLine: { lineStyle: { color: cor.borderForte } },
          axisLabel: { color: cor.muted, fontSize: 10 },
        },
        yAxis: { type: 'value', show: false },
        series: [{
          type: 'bar',
          data: kit.distribuicao_por_mes.map((m) => ({
            value: m.valor,
            itemStyle: { color: picos.has(m.mes) ? cor.wine : cor.borderForte },
          })),
        }],
      }}
    />
  )
}

export function KitsTematicos({ dados }: { dados: Kits | undefined }) {
  if (!dados) return <Card titulo="Kits de produtos"><div className="mut">Carregando...</div></Card>
  if (!dados.disponivel) {
    return (
      <Card titulo="Kits de produtos">
        <Vazio icone={null} titulo={dados.motivo} />
      </Card>
    )
  }

  return (
    <Card
      titulo="Kits de produtos"
      acoes={
        <ComoFoiCalculado
          calculo={{
            titulo: 'Como os kits foram encontrados',
            formula: dados.calculo.formula,
            valores: Object.entries(dados.calculo.valores ?? {}).map(([rotulo, valor]) => ({
              rotulo,
              valor: String(valor),
            })),
            premissas: dados.calculo.premissas,
          }}
        />
      }
    >
      {dados.itens.length === 0 ? (
        <Vazio icone={null} titulo="Nenhum kit com afinidade forte o bastante neste recorte." />
      ) : (
        <div className="pilha" style={{ gap: 12 }}>
          <Aviso tipo="info">
            Grupos de 3 ou mais produtos onde <b>todo par</b> tem afinidade forte entre
            si — não só cada um com um produto central. O sistema <b>não nomeia o
            tema</b> ("combo inverno", "combo imunidade"): a base não tem essa
            marcação. O gráfico mostra em qual mês o kit historicamente vende mais
            (barras destacadas = os 3 picos), para você reconhecer o padrão.
            {dados.n_anos_historico < 2 && (
              <> Este cliente tem só {dados.n_anos_historico} ano de histórico —
              um pico pode ser evento pontual, não sazonalidade de verdade.</>
            )}
          </Aviso>
          <div className="grade c2">
            {dados.itens.map((kit, i) => (
              <div key={i} className="claim fato" style={{ margin: 0 }}>
                <div className="linha entre" style={{ alignItems: 'flex-start' }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>
                    {kit.produtos.map((p) => p.produto).join(' + ')}
                  </div>
                  <span className="mut" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>
                    afinidade {kit.afinidade_media.toFixed(1)}×
                  </span>
                </div>
                <div className="mut" style={{ fontSize: 12, margin: '6px 0' }}>
                  Picos históricos: <b>{kit.picos_mes_nome.join(', ')}</b> ·{' '}
                  {brl(kit.faturamento_periodo_selecionado)} no período selecionado
                </div>
                <GraficoSazonalidade kit={kit} />
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  )
}
