import { useMutation, useQuery } from '@tanstack/react-query'
import { Download, LineChart, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { Grafico, useCoresGrafico } from '../components/Grafico'
import { ComoFoiCalculado } from '../components/ComoFoiCalculado'
import { Th, useOrdenacao } from '../components/Tabela'
import { SeletorPeriodo } from '../components/dashboard/SeletorPeriodo'
import { SeletorUF } from '../components/dashboard/SeletorUF'
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

  const [uf, setUf] = useState<string | undefined>(undefined)
  // Faixa em drill-down. Começa em monoproduto (1 SKU) para o card já nascer
  // com conteúdo em vez de um vazio pedindo clique.
  const [faixa, setFaixa] = useState<{ min: number; max: number | null }>({ min: 1, max: 1 })

  const p = periodo
  const habilitado = !!p

  const { data: ufs } = useQuery({
    queryKey: ['analytics', 'uf', clienteId, p?.ini, p?.fim],
    queryFn: () => analytics.uf(clienteId, p!.ini, p!.fim),
    enabled: habilitado,
  })
  const { data: mix } = useQuery({
    queryKey: ['analytics', 'mix', clienteId, p?.ini, p?.fim, uf ?? ''],
    queryFn: () => analytics.mix(clienteId, p!.ini, p!.fim, uf),
    enabled: habilitado,
  })
  const { data: detalhe } = useQuery({
    queryKey: ['analytics', 'mix-faixa', clienteId, p?.ini, p?.fim, uf ?? '', faixa.min, faixa.max ?? ''],
    queryFn: () => analytics.mixFaixa(clienteId, p!.ini, p!.fim, faixa.min, faixa.max ?? undefined, uf),
    enabled: habilitado,
  })
  const { data: alto } = useQuery({
    queryKey: ['analytics', 'mix-alto', clienteId, p?.ini, p?.fim, uf ?? ''],
    queryFn: () => analytics.mixAlto(clienteId, p!.ini, p!.fim, 10, uf),
    enabled: habilitado,
  })
  const { data: expansao } = useQuery({
    queryKey: ['analytics', 'mix-expansao', clienteId, p?.ini, p?.fim, uf ?? ''],
    queryFn: () => analytics.mixOportunidades(clienteId, p!.ini, p!.fim, uf),
    enabled: habilitado,
  })

  const { itens: itensProd, ordem: ordemProd, alternar: alternarProd } = useOrdenacao(
    detalhe?.disponivel ? detalhe.top_produtos : [],
  )
  const { itens: itensPdv, ordem: ordemPdv, alternar: alternarPdv } = useOrdenacao(
    detalhe?.disponivel ? detalhe.itens : [],
  )
  const { itens: itensExpansao, ordem: ordemExp, alternar: alternarExp } = useOrdenacao(
    expansao?.disponivel ? expansao.itens : [],
  )

  // O resumo devolve sku_max=null para a faixa aberta (10+); o drill-down
  // precisa do mesmo par para a seleção casar com a linha clicada.
  const selecionarFaixa = (rotulo: string) => {
    const f = mix?.disponivel ? mix.resumo.find((r) => r.faixa === rotulo) : undefined
    if (f) setFaixa({ min: f.sku_min, max: f.sku_max })
  }
  const faixaAtiva = (min: number, max: number | null) =>
    faixa.min === min && faixa.max === max

  const exportar = useMutation({
    mutationFn: () => analytics.mixXlsx(clienteId, p!.ini, p!.fim, uf, faixa.min, faixa.max ?? undefined),
  })

  if (carregandoDisp || !disp) return <Card><div className="mut">Carregando...</div></Card>

  return (
    <>
      <header>
        <div className="linha entre">
          <div>
            <h1>Mix de PDV — {disp.cliente}</h1>
            <p className="dek">Quantos SKUs distintos cada PDV compra, e o quanto isso vale.</p>
          </div>
          <div className="linha" style={{ gap: 10, alignItems: 'flex-end' }}>
            <button disabled={exportar.isPending || !habilitado} onClick={() => exportar.mutate()}>
              <Download size={14} />
              {exportar.isPending ? 'Gerando...' : 'Exportar Excel'}
            </button>
            <SeletorUF ufs={ufs} valor={uf} aoMudar={setUf} />
            <select value={clienteId} onChange={(e) => setClienteAtual(Number(e.target.value))} style={{ width: 200 }}>
              {clientes.map((c) => (<option key={c.id} value={c.id}>{c.nome}</option>))}
            </select>
          </div>
        </div>
        {exportar.isError && (
          <Aviso tipo="atencao">{(exportar.error as Error).message}</Aviso>
        )}
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
                <div className="mut" style={{ fontSize: 12, marginBottom: 8 }}>
                  Clique numa faixa para ver quem está nela e o que ela compra.
                </div>
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
                      <tr
                        key={f.faixa}
                        onClick={() => setFaixa({ min: f.sku_min, max: f.sku_max })}
                        style={{
                          cursor: 'pointer',
                          background: faixaAtiva(f.sku_min, f.sku_max)
                            ? 'var(--sel, rgba(127,29,29,.08))' : undefined,
                        }}
                      >
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
                  aoClicar={(nome) => selecionarFaixa(nome)}
                  opcoes={{
                    xAxis: { type: 'category', data: mix.resumo.map((f) => f.faixa),
                             axisLine: { lineStyle: { color: cor.borderForte } },
                             axisLabel: { color: cor.muted } },
                    yAxis: { type: 'value', axisLabel: { color: cor.muted },
                             splitLine: { lineStyle: { color: cor.border } } },
                    series: [{
                      type: 'bar',
                      data: mix.resumo.map((f) => ({
                        value: f.rs_por_pdv ?? 0,
                        itemStyle: {
                          color: faixaAtiva(f.sku_min, f.sku_max) ? cor.wine : cor.borderForte,
                        },
                      })),
                    }],
                  }}
                />
              </Card>
            </>
          )}

          <Card
            titulo={
              detalhe?.disponivel
                ? `Faixa em análise: ${detalhe.faixa}`
                : 'Faixa em análise'
            }
            acoes={
              mix?.disponivel ? (
                <div className="linha" style={{ gap: 6, flexWrap: 'wrap' }}>
                  {mix.resumo.map((f) => (
                    <button
                      key={f.faixa}
                      className={faixaAtiva(f.sku_min, f.sku_max) ? 'primario' : ''}
                      onClick={() => setFaixa({ min: f.sku_min, max: f.sku_max })}
                    >
                      {f.faixa}
                    </button>
                  ))}
                </div>
              ) : undefined
            }
          >
            {!detalhe ? (
              <div className="mut">Carregando...</div>
            ) : !detalhe.disponivel ? (
              <Vazio icone={null} titulo={detalhe.motivo} />
            ) : detalhe.n_pdvs === 0 ? (
              <Vazio icone={null} titulo="Nenhum PDV nesta faixa no período." />
            ) : (
              <div className="pilha" style={{ gap: 14 }}>
                <div className="kpis">
                  <Kpi rotulo="PDVs na faixa" valor={inteiro(detalhe.n_pdvs)} />
                  <Kpi rotulo="Faturamento" valor={brl(detalhe.faturamento)}
                       sub={`${pct(detalhe.participacao_pct)} do total`} />
                  <Kpi rotulo="R$/PDV" valor={brl(detalhe.rs_por_pdv)} />
                  {detalhe.mix_medio != null && (
                    <Kpi rotulo="Mix médio" valor={`${detalhe.mix_medio.toFixed(1)} SKUs`} />
                  )}
                </div>

                <div className="grade c2">
                  <div>
                    <div className="rot" style={{ marginBottom: 6 }}>
                      O que esta faixa compra
                    </div>
                    <div className="mut" style={{ fontSize: 12, marginBottom: 6 }}>
                      Em quantos PDVs <b>da faixa</b> cada produto aparece.
                    </div>
                    <div className="rolagem">
                      <table>
                        <thead>
                          <tr>
                            <Th campo="produto" ordem={ordemProd} alternar={alternarProd}>Produto</Th>
                            <Th campo="n_pdvs" ordem={ordemProd} alternar={alternarProd} num>PDVs</Th>
                            <Th campo="pct_da_faixa" ordem={ordemProd} alternar={alternarProd} num>% da faixa</Th>
                            <Th campo="faturamento" ordem={ordemProd} alternar={alternarProd} num>Faturamento</Th>
                          </tr>
                        </thead>
                        <tbody>
                          {itensProd.map((tp) => (
                            <tr key={tp.produto_id}>
                              <td>{tp.produto}</td>
                              <td className="num">{inteiro(tp.n_pdvs)}</td>
                              <td className="num">{pct(tp.pct_da_faixa)}</td>
                              <td className="num">{brl(tp.faturamento)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div>
                    <div className="rot" style={{ marginBottom: 6 }}>
                      Quais PDVs estão nela
                    </div>
                    <div className="mut" style={{ fontSize: 12, marginBottom: 6 }}>
                      {detalhe.n_mostrados != null && detalhe.n_mostrados < detalhe.n_pdvs
                        ? `Os ${inteiro(detalhe.n_mostrados)} maiores por faturamento, de ${inteiro(detalhe.n_pdvs)}.`
                        : `Todos os ${inteiro(detalhe.n_pdvs)}.`}
                    </div>
                    <div className="rolagem" style={{ maxHeight: 420, overflowY: 'auto' }}>
                      <table>
                        <thead>
                          <tr>
                            <Th campo="pdv" ordem={ordemPdv} alternar={alternarPdv}>PDV</Th>
                            <Th campo="uf" ordem={ordemPdv} alternar={alternarPdv}>UF</Th>
                            <Th campo="n_skus" ordem={ordemPdv} alternar={alternarPdv} num>SKUs</Th>
                            <Th campo="faturamento" ordem={ordemPdv} alternar={alternarPdv} num>Faturamento</Th>
                          </tr>
                        </thead>
                        <tbody>
                          {itensPdv.map((it) => (
                            <tr key={it.pdv_id}>
                              <td>{it.pdv}</td>
                              <td className="mut">{it.uf ?? '—'}</td>
                              <td className="num">{inteiro(it.n_skus)}</td>
                              <td className="num">{brl(it.faturamento)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
            )}
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
