import { ComoFoiCalculado } from '../ComoFoiCalculado'
import { Grafico, useCoresGrafico } from '../Grafico'
import { Th, useOrdenacao } from '../Tabela'
import { Aviso, Card, Kpi, Tag, Vazio } from '../ui'
import type { ABCMercado } from '../../lib/analytics'
import { brl, inteiro, pct } from '../../lib/format'

const SITUACAO_TAG: Record<string, string> = {
  OPORTUNIDADE: 't-erro',
  EM_LINHA: 't-ok',
  ACIMA_DO_MERCADO: 't-hip',
}
const SITUACAO_ROTULO: Record<string, string> = {
  OPORTUNIDADE: 'oportunidade',
  EM_LINHA: 'em linha',
  ACIMA_DO_MERCADO: 'acima do mercado',
}

function TagClasse({ c }: { c: string }) {
  return <Tag tipo={c === 'A' ? 't-fato' : c === 'B' ? 't-hip' : 't-neutro'}>{c}</Tag>
}

export function ComparativoMercado({ dados }: { dados: ABCMercado | undefined }) {
  const cor = useCoresGrafico()
  const { itens: oport, ordem, alternar } = useOrdenacao(
    dados?.disponivel ? dados.oportunidades : [],
  )

  if (!dados) return <Card titulo="Curva ABC × mercado"><div className="mut">Carregando...</div></Card>
  if (!dados.disponivel) {
    return (
      <Card titulo="Curva ABC × mercado">
        <Vazio icone={null} titulo={dados.motivo} />
      </Card>
    )
  }

  const recorte = dados.uf ?? 'país'
  // "em RJ" x "no país": a preposição muda com o recorte.
  const emRecorte = dados.uf ? `em ${dados.uf}` : 'no país'
  // As duas curvas têm quantidades de produtos diferentes. O eixo é a posição
  // no ranking de cada uma — é a FORMA (quão concentrada) que se compara, não
  // o produto que ocupa a posição N em cada lado.
  const maxPos = Math.max(
    dados.curva_cliente.length,
    dados.curva_mercado.length,
  )

  return (
    <div className="pilha">
      <Card
        titulo={`Curva ABC × mercado Vitamedic (${recorte})`}
        acoes={
          <ComoFoiCalculado
            calculo={{
              titulo: 'Como a comparação foi feita',
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
        <div className="pilha" style={{ gap: 12 }}>
          <div className="kpis">
            <Kpi
              rotulo="Share no Vitamedic"
              valor={dados.share_no_vitamedic_pct != null ? pct(dados.share_no_vitamedic_pct) : '—'}
              sub={`da venda Vitamedic ${emRecorte} passa por este cliente`}
            />
            <Kpi
              rotulo="Em linha com o mercado"
              valor={inteiro(dados.por_situacao.EM_LINHA ?? 0)}
              sub="mesma classe nas duas curvas"
            />
            <Kpi
              rotulo="Oportunidades"
              valor={inteiro(dados.por_situacao.OPORTUNIDADE ?? 0)}
              sub="mercado valoriza mais que o cliente"
            />
            <Kpi
              rotulo="Acima do mercado"
              valor={inteiro(dados.por_situacao.ACIMA_DO_MERCADO ?? 0)}
              sub="cliente valoriza mais que o mercado"
            />
          </div>

          <Aviso tipo="info">
            As duas curvas usam o mesmo critério, mas medem elos diferentes: o cliente é
            sell-out (distribuidor&nbsp;→&nbsp;PDV) e o mercado é PDV&nbsp;→&nbsp;consumidor,
            no período do arquivo IQVIA. Compare a <b>forma da curva</b> e a{' '}
            <b>importância relativa</b> de cada produto — não os valores absolutos.
          </Aviso>

          <div>
            <div className="rot" style={{ marginBottom: 6 }}>
              Concentração acumulada — quanto mais à esquerda a curva sobe, mais
              concentrada em poucos produtos
            </div>
            <Grafico
              altura={300}
              opcoes={{
                tooltip: { trigger: 'axis' },
                legend: {
                  data: ['Cliente', `Mercado Vitamedic (${recorte})`],
                  textStyle: { color: cor.muted },
                },
                xAxis: {
                  type: 'category',
                  name: 'produtos (ranking)',
                  nameLocation: 'middle',
                  nameGap: 26,
                  nameTextStyle: { color: cor.muted },
                  data: Array.from({ length: maxPos }, (_, i) => String(i + 1)),
                  axisLine: { lineStyle: { color: cor.borderForte } },
                  axisLabel: { color: cor.muted },
                },
                yAxis: {
                  type: 'value',
                  max: 100,
                  name: '% acumulado',
                  nameTextStyle: { color: cor.muted },
                  axisLabel: { color: cor.muted, formatter: '{value}%' },
                  splitLine: { lineStyle: { color: cor.border } },
                },
                series: [
                  {
                    name: 'Cliente',
                    type: 'line',
                    showSymbol: false,
                    data: dados.curva_cliente.map((p) => p.acumulada_pct),
                    lineStyle: { color: cor.wine, width: 2 },
                    itemStyle: { color: cor.wine },
                  },
                  {
                    name: `Mercado Vitamedic (${recorte})`,
                    type: 'line',
                    showSymbol: false,
                    data: dados.curva_mercado.map((p) => p.acumulada_pct),
                    lineStyle: { color: cor.muted, width: 2, type: 'dashed' },
                    itemStyle: { color: cor.muted },
                  },
                ],
              }}
            />
          </div>

          <div className="mut" style={{ fontSize: 12 }}>
            {inteiro(dados.n_ligados)} produtos ligados ao mercado
            {dados.cobertura_da_ponte_pct != null && (
              <> ({pct(dados.cobertura_da_ponte_pct)} do faturamento do cliente)</>
            )}
            . {inteiro(dados.n_sem_correspondencia)} não casaram por apresentação e ficam
            fora da comparação. O mercado Vitamedic {emRecorte} tem{' '}
            {inteiro(dados.n_produtos_mercado)} produtos e{' '}
            {brl(dados.valor_mercado_total)}.
          </div>
        </div>
      </Card>

      <Card titulo="Onde há oportunidade">
        {oport.length === 0 ? (
          <Vazio
            icone={null}
            titulo="Nenhum produto em que o mercado valorize mais do que o cliente."
          />
        ) : (
          <div className="pilha" style={{ gap: 8 }}>
            <Aviso tipo="atencao">
              Produtos que pesam <b>mais na curva do mercado</b> do que na curva deste
              cliente. É um sinal para investigar, não uma meta: pode haver
              exclusividade, logística ou acordo comercial que o dado não mostra.
            </Aviso>
            <div className="rolagem">
              <table>
                <thead>
                  <tr>
                    <Th campo="produto" ordem={ordem} alternar={alternar}>Produto</Th>
                    <Th campo="classe_cliente" ordem={ordem} alternar={alternar}>Cliente</Th>
                    <Th campo="classe_mercado" ordem={ordem} alternar={alternar}>Mercado</Th>
                    <Th campo="faturamento_cliente" ordem={ordem} alternar={alternar} num>Faturamento</Th>
                    <Th campo="valor_mercado" ordem={ordem} alternar={alternar} num>Mercado</Th>
                    <Th
                      campo="share_no_vitamedic_pct"
                      ordem={ordem}
                      alternar={alternar}
                      num
                      titulo="Quanto da venda Vitamedic deste produto na região passa por este cliente"
                    >
                      Share
                    </Th>
                  </tr>
                </thead>
                <tbody>
                  {oport.map((i) => (
                    <tr key={i.produto_id}>
                      <td>{i.produto}</td>
                      <td><TagClasse c={i.classe_cliente} /></td>
                      <td><TagClasse c={i.classe_mercado} /></td>
                      <td className="num">{brl(i.faturamento_cliente)}</td>
                      <td className="num">{brl(i.valor_mercado)}</td>
                      <td className="num" style={{ fontWeight: 600 }}>
                        {i.share_no_vitamedic_pct != null ? pct(i.share_no_vitamedic_pct) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Card>

      <Card titulo="Produto a produto">
        <div className="rolagem" style={{ maxHeight: 480, overflowY: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th>Produto</th>
                <th>Cliente</th>
                <th>Mercado</th>
                <th></th>
                <th className="num">Peso no cliente</th>
                <th className="num">Peso no mercado</th>
                <th className="num">Share</th>
              </tr>
            </thead>
            <tbody>
              {dados.itens.map((i) => (
                <tr key={i.produto_id}>
                  <td>{i.produto}</td>
                  <td><TagClasse c={i.classe_cliente} /></td>
                  <td><TagClasse c={i.classe_mercado} /></td>
                  <td>
                    <Tag tipo={SITUACAO_TAG[i.situacao] ?? 't-neutro'}>
                      {SITUACAO_ROTULO[i.situacao] ?? i.situacao}
                    </Tag>
                  </td>
                  <td className="num">
                    {i.participacao_cliente_pct != null ? pct(i.participacao_cliente_pct) : '—'}
                  </td>
                  <td className="num">{pct(i.participacao_mercado_pct)}</td>
                  <td className="num">
                    {i.share_no_vitamedic_pct != null ? pct(i.share_no_vitamedic_pct) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
