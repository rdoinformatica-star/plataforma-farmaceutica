import { useQuery } from '@tanstack/react-query'
import { LineChart, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { Grafico, useCoresGrafico } from '../components/Grafico'
import { ComoFoiCalculado } from '../components/ComoFoiCalculado'
import { Th, useOrdenacao } from '../components/Tabela'
import { SeletorPeriodo } from '../components/dashboard/SeletorPeriodo'
import { Aviso, Card, Kpi, Vazio } from '../components/ui'
import { analytics } from '../lib/analytics'
import { api, type Cliente } from '../lib/api'
import { brl, inteiro, pct } from '../lib/format'
import { useEstado } from '../lib/estado'
import type { Periodo } from '../lib/periodo'
import { resolverPreset } from '../lib/periodo'

export function Mix() {
  const { clienteAtual, setClienteAtual } = useEstado()
  const { data: clientes } = useQuery({
    queryKey: ['clientes', 'ativos'],
    queryFn: () => api.get<Cliente[]>('/clientes?ativo=true'),
  })

  if (!clienteAtual) {
    return (
      <>
        <header>
          <h1>Mix de PDV</h1>
          <p className="dek">Escolha um cliente para ver quantos SKUs cada PDV compra.</p>
        </header>
        <Card>
          <Vazio icone={<Users size={36} />} titulo="Nenhum cliente selecionado"
                acao={clientes?.length ? (
                  <div className="linha" style={{ gap: 8, justifyContent: 'center', flexWrap: 'wrap' }}>
                    {clientes.map((c) => (
                      <button key={c.id} className="primario" onClick={() => setClienteAtual(c.id)}>{c.nome}</button>
                    ))}
                  </div>
                ) : <Link to="/clientes">Cadastre um cliente primeiro</Link>} />
        </Card>
      </>
    )
  }
  return <MixCliente clienteId={clienteAtual} clientes={clientes ?? []} />
}

function MixCliente({ clienteId, clientes }: { clienteId: number; clientes: Cliente[] }) {
  const { setClienteAtual } = useEstado()
  const cor = useCoresGrafico()
  const { data: disp, isLoading: carregandoDisp } = useQuery({
    queryKey: ['analytics', 'disponibilidade', clienteId],
    queryFn: () => analytics.disponibilidade(clienteId),
  })

  const disponivel: Periodo | null = disp?.periodo_min
    ? { ini: disp.periodo_min, fim: disp.periodo_max! } : null
  const [periodo, setPeriodo] = useState<Periodo | null>(null)
  useEffect(() => {
    if (disponivel && !periodo) setPeriodo(resolverPreset('semestre', disponivel))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disponivel?.ini, disponivel?.fim])

  const p = periodo
  const habilitado = !!p

  const { data: mix } = useQuery({
    queryKey: ['analytics', 'mix', clienteId, p?.ini, p?.fim],
    queryFn: () => analytics.mix(clienteId, p!.ini, p!.fim),
    enabled: habilitado,
  })
  const { data: mono } = useQuery({
    queryKey: ['analytics', 'mix-mono', clienteId, p?.ini, p?.fim],
    queryFn: () => analytics.mixMonoproduto(clienteId, p!.ini, p!.fim),
    enabled: habilitado,
  })
  const { data: alto } = useQuery({
    queryKey: ['analytics', 'mix-alto', clienteId, p?.ini, p?.fim],
    queryFn: () => analytics.mixAlto(clienteId, p!.ini, p!.fim),
    enabled: habilitado,
  })
  const { data: expansao } = useQuery({
    queryKey: ['analytics', 'mix-expansao', clienteId, p?.ini, p?.fim],
    queryFn: () => analytics.mixOportunidades(clienteId, p!.ini, p!.fim),
    enabled: habilitado,
  })

  const { itens: itensMono, ordem: ordemMono, alternar: alternarMono } = useOrdenacao(
    mono?.disponivel ? mono.top_produtos.slice(0, 5) : [],
  )
  const { itens: itensExpansao, ordem: ordemExp, alternar: alternarExp } = useOrdenacao(
    expansao?.disponivel ? expansao.itens : [],
  )

  if (carregandoDisp || !disp) return <Card><div className="mut">Carregando...</div></Card>

  return (
    <>
      <header>
        <div className="linha entre">
          <div>
            <h1>Mix de PDV — {disp.cliente}</h1>
            <p className="dek">Quantos SKUs distintos cada PDV compra, e o quanto isso vale.</p>
          </div>
          <select value={clienteId} onChange={(e) => setClienteAtual(Number(e.target.value))} style={{ width: 200 }}>
            {clientes.map((c) => (<option key={c.id} value={c.id}>{c.nome}</option>))}
          </select>
        </div>
      </header>

      {!disp.tem_sellout ? (
        <Card>
          <Vazio icone={<LineChart size={36} />} titulo="Este cliente ainda não possui dados suficientes para esta análise."
                acao={<Link to="/importar" className="btn primario">Importar um relatório</Link>}>
            {disp.motivo_indisponivel}
          </Vazio>
        </Card>
      ) : (
        <div className="pilha">
          {disponivel && <SeletorPeriodo disponivel={disponivel} valor={periodo ?? disponivel} aoMudar={setPeriodo} />}

          {mix?.disponivel && (
            <>
              <div className="kpis">
                <Kpi rotulo="PDVs no período" valor={inteiro(mix.total_pdvs)} />
                <Kpi rotulo="Mix médio" valor={`${mix.mix_medio} SKUs`} />
                <Kpi rotulo="Mix mediano" valor={`${mix.mix_mediano} SKUs`} />
              </div>

              <Card titulo="Resumo por faixa de mix" acoes={
                <ComoFoiCalculado calculo={{
                  titulo: 'Como o mix foi calculado', formula: mix.calculo.formula,
                  valores: Object.entries(mix.calculo.valores ?? {}).map(([rotulo, valor]) => ({ rotulo, valor: String(valor) })),
                  premissas: mix.calculo.premissas,
                }} />
              }>
                <table>
                  <thead>
                    <tr>
                      <th>Faixa</th><th className="num">PDVs</th><th className="num">% PDVs</th>
                      <th className="num">Faturamento</th><th className="num">% faturamento</th>
                      <th className="num">R$/PDV</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mix.resumo.map((f) => (
                      <tr key={f.faixa}>
                        <td style={{ fontWeight: 600 }}>{f.faixa}</td>
                        <td className="num">{inteiro(f.n_pdvs)}</td>
                        <td className="num">{pct(f.pct_pdvs)}</td>
                        <td className="num">{brl(f.faturamento)}</td>
                        <td className="num">{pct(f.pct_faturamento)}</td>
                        <td className="num" style={{ fontWeight: 600 }}>{brl(f.rs_por_pdv)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>

              <Card titulo="Produtividade por faixa (R$/PDV)">
                <Grafico
                  opcoes={{
                    xAxis: { type: 'category', data: mix.resumo.map((f) => f.faixa),
                             axisLine: { lineStyle: { color: cor.borderForte } },
                             axisLabel: { color: cor.muted } },
                    yAxis: { type: 'value', axisLabel: { color: cor.muted },
                             splitLine: { lineStyle: { color: cor.border } } },
                    series: [{ type: 'bar', data: mix.resumo.map((f) => f.rs_por_pdv ?? 0),
                              itemStyle: { color: cor.wine } }],
                  }}
                />
              </Card>
            </>
          )}

          <div className="grade c2">
            <Card titulo="PDVs monoproduto (1 SKU)">
              {mono?.disponivel ? (
                <div className="pilha">
                  <div className="kpis">
                    <Kpi rotulo="PDVs" valor={inteiro(mono.n_pdvs)} />
                    <Kpi rotulo="R$/PDV" valor={brl(mono.rs_por_pdv)} />
                  </div>
                  {mono.top_produtos.length > 0 && (
                    <div>
                      <div className="rot" style={{ marginBottom: 6 }}>Produtos mais concentradores</div>
                      <table>
                        <thead>
                          <tr>
                            <Th campo="produto" ordem={ordemMono} alternar={alternarMono}>Produto</Th>
                            <Th campo="n_pdvs" ordem={ordemMono} alternar={alternarMono} num>PDVs</Th>
                          </tr>
                        </thead>
                        <tbody>
                          {itensMono.map((tp) => (
                            <tr key={tp.produto_id}>
                              <td>{tp.produto}</td>
                              <td className="num">{tp.n_pdvs} PDVs</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ) : <div className="mut">Carregando...</div>}
            </Card>

            <Card titulo="PDVs estratégicos de alto mix (10+ SKUs)">
              {alto?.disponivel ? (
                <div className="kpis">
                  <Kpi rotulo="PDVs" valor={inteiro(alto.n_pdvs)} />
                  <Kpi rotulo="Participação" valor={pct(alto.participacao_pct)} />
                  <Kpi rotulo="R$/PDV" valor={brl(alto.rs_por_pdv)} />
                </div>
              ) : <div className="mut">Carregando...</div>}
            </Card>
          </div>

          <Card titulo="Oportunidades de expansão de mix">
            {expansao?.disponivel ? (
              expansao.itens.length === 0 ? (
                <Vazio icone={null} titulo="Nenhuma oportunidade de expansão identificada neste período." />
              ) : (
                <div className="pilha" style={{ gap: 8 }}>
                  <Aviso tipo="info">
                    PDV com mix baixo cujo faturamento já iguala a média de R$/PDV da
                    faixa seguinte — não é uma previsão de compra, é uma leitura de
                    similaridade a investigar.
                  </Aviso>
                  <div className="rolagem">
                    <table>
                      <thead>
                        <tr>
                          <Th campo="pdv" ordem={ordemExp} alternar={alternarExp}>PDV</Th>
                          <Th campo="faixa_atual" ordem={ordemExp} alternar={alternarExp}>Mix atual</Th>
                          <Th campo="faixa_referencia" ordem={ordemExp} alternar={alternarExp}>Faixa de referência</Th>
                          <Th campo="faturamento_atual" ordem={ordemExp} alternar={alternarExp} num>Faturamento</Th>
                          <Th campo="rs_por_pdv_faixa_referencia" ordem={ordemExp} alternar={alternarExp} num>R$/PDV de referência</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {itensExpansao.map((it) => (
                          <tr key={it.pdv_id}>
                            <td>{it.pdv}</td>
                            <td>{it.faixa_atual} ({it.n_skus_atual})</td>
                            <td>{it.faixa_referencia}</td>
                            <td className="num">{brl(it.faturamento_atual)}</td>
                            <td className="num">{brl(it.rs_por_pdv_faixa_referencia)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )
            ) : <div className="mut">Carregando...</div>}
          </Card>
        </div>
      )}
    </>
  )
}
