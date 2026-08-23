import { useQuery } from '@tanstack/react-query'
import { LineChart, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { Grafico, useCoresGrafico } from '../components/Grafico'
import { ComoFoiCalculado } from '../components/ComoFoiCalculado'
import { ComparativoMercado } from '../components/abc/ComparativoMercado'
import { Th, useOrdenacao } from '../components/Tabela'
import { SeletorPeriodo } from '../components/dashboard/SeletorPeriodo'
import { Aviso, Card, Kpi, Tag, Vazio } from '../components/ui'
import { analytics, type FaixaCrescimento } from '../lib/analytics'
import { api, type Cliente } from '../lib/api'
import { brl, inteiro, pct } from '../lib/format'
import { useEstado } from '../lib/estado'
import type { Periodo } from '../lib/periodo'
import { resolverPreset } from '../lib/periodo'

const CLASSE_TAG: Record<string, string> = { A: 't-fato', B: 't-hip', C: 't-neutro' }
const FAIXA_ROTULO: Record<FaixaCrescimento, string> = {
  CRESCENDO: 'Crescendo', ESTAVEL: 'Estável', CAINDO: 'Caindo',
  NOVO: 'Novo', SEM_HISTORICO: 'Sem histórico',
}
const FAIXA_EMOJI: Record<string, string> = { A: '🔥', B: '📈', C: '💡' }

export function ABC() {
  const { clienteAtual, setClienteAtual } = useEstado()
  const { data: clientes } = useQuery({
    queryKey: ['clientes', 'ativos'],
    queryFn: () => api.get<Cliente[]>('/clientes?ativo=true'),
  })

  if (!clienteAtual) {
    return (
      <>
        <header>
          <h1>Curva ABC</h1>
          <p className="dek">Escolha um cliente para classificar os produtos por faturamento.</p>
        </header>
        <Card>
          <Vazio
            icone={<Users size={36} />}
            titulo="Nenhum cliente selecionado"
            acao={
              clientes?.length ? (
                <div className="linha" style={{ gap: 8, justifyContent: 'center', flexWrap: 'wrap' }}>
                  {clientes.map((c) => (
                    <button key={c.id} className="primario" onClick={() => setClienteAtual(c.id)}>
                      {c.nome}
                    </button>
                  ))}
                </div>
              ) : (
                <Link to="/clientes">Cadastre um cliente primeiro</Link>
              )
            }
          />
        </Card>
      </>
    )
  }

  return <ABCCliente clienteId={clienteAtual} clientes={clientes ?? []} />
}

function ABCCliente({ clienteId, clientes }: { clienteId: number; clientes: Cliente[] }) {
  const { setClienteAtual } = useEstado()
  const cor = useCoresGrafico()
  const { data: disp, isLoading: carregandoDisp } = useQuery({
    queryKey: ['analytics', 'disponibilidade', clienteId],
    queryFn: () => analytics.disponibilidade(clienteId),
  })

  const disponivel: Periodo | null = disp?.periodo_min
    ? { ini: disp.periodo_min, fim: disp.periodo_max! }
    : null
  const [periodo, setPeriodo] = useState<Periodo | null>(null)
  useEffect(() => {
    if (disponivel && !periodo) setPeriodo(resolverPreset('semestre', disponivel))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disponivel?.ini, disponivel?.fim])

  const [limiteA, setLimiteA] = useState(80)
  const [limiteB, setLimiteB] = useState(95)
  const [uf, setUf] = useState<string | undefined>(undefined)
  const p = periodo
  const habilitado = !!p

  const { data: curva } = useQuery({
    queryKey: ['analytics', 'abc', clienteId, p?.ini, p?.fim, limiteA, limiteB, uf],
    queryFn: () => analytics.abc(clienteId, p!.ini, p!.fim, limiteA, limiteB, uf),
    enabled: habilitado,
  })
  const { data: matriz } = useQuery({
    queryKey: ['analytics', 'abc-crescimento', clienteId, p?.ini, p?.fim, uf],
    queryFn: () => analytics.abcCrescimento(clienteId, p!.ini, p!.fim, uf),
    enabled: habilitado,
  })
  const { data: vsMercado } = useQuery({
    queryKey: ['analytics', 'abc-mercado', clienteId, p?.ini, p?.fim, limiteA, limiteB, uf],
    queryFn: () => analytics.abcMercado(clienteId, p!.ini, p!.fim, limiteA, limiteB, uf),
    enabled: habilitado,
  })

  const { itens: itensCurva, ordem: ordemCurva, alternar: alternarCurva } = useOrdenacao(
    curva?.disponivel ? curva.itens.slice(0, 100) : [],
  )

  // Share por produto vem da comparação com o mercado (base diferente da curva);
  // indexa por produto para enriquecer a tabela sem refazer a conta.
  const sharePorProduto = new Map<number, number | null>()
  if (vsMercado?.disponivel) {
    for (const i of vsMercado.itens) sharePorProduto.set(i.produto_id, i.share_no_vitamedic_pct)
  }
  const temShare = sharePorProduto.size > 0

  if (carregandoDisp || !disp) return <Card><div className="mut">Carregando...</div></Card>

  return (
    <>
      <header>
        <div className="linha entre">
          <div>
            <h1>Curva ABC — {disp.cliente}</h1>
            <p className="dek">Classificação de produtos pelo faturamento acumulado.</p>
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

          <Card titulo="Parâmetros">
            <div className="linha" style={{ gap: 16, flexWrap: 'wrap' }}>
              <label style={{ width: 140, marginBottom: 0 }}>
                <span>Limite A (%)</span>
                <input type="number" min={1} max={99} value={limiteA}
                       onChange={(e) => setLimiteA(Number(e.target.value))} />
              </label>
              <label style={{ width: 140, marginBottom: 0 }}>
                <span>Limite B (%)</span>
                <input type="number" min={1} max={100} value={limiteB}
                       onChange={(e) => setLimiteB(Number(e.target.value))} />
              </label>
              {disp.tem_uf && (
                <label style={{ width: 140, marginBottom: 0 }}>
                  <span>UF</span>
                  <select value={uf ?? ''} onChange={(e) => setUf(e.target.value || undefined)}>
                    <option value="">Todas</option>
                    <option value="RJ">RJ</option>
                    <option value="ES">ES</option>
                    <option value="SP">SP</option>
                    <option value="MG">MG</option>
                  </select>
                </label>
              )}
            </div>
          </Card>

          {curva && !curva.disponivel && <Aviso tipo="atencao">{curva.motivo}</Aviso>}

          {curva?.disponivel && (
            <>
              <div className="kpis">
                {(['A', 'B', 'C'] as const).map((c) => (
                  <Kpi key={c} rotulo={`Classe ${c}`}
                       valor={`${curva.resumo[c].n_produtos} produtos`}
                       sub={`${pct(curva.resumo[c].pct_faturamento)} do faturamento`} />
                ))}
              </div>

              <Card titulo="Concentração do faturamento (curva ABC)">
                <Grafico
                  altura={300}
                  opcoes={{
                    xAxis: { type: 'category', data: curva.itens.slice(0, 40).map((_, i) => i + 1),
                             name: 'produtos (ordenados por faturamento)',
                             axisLine: { lineStyle: { color: cor.borderForte } },
                             axisLabel: { color: cor.muted } },
                    yAxis: [
                      { type: 'value', name: 'faturamento', axisLabel: { color: cor.muted },
                        splitLine: { lineStyle: { color: cor.border } } },
                      { type: 'value', name: '% acumulado', max: 100,
                        axisLabel: { color: cor.muted }, splitLine: { show: false } },
                    ],
                    series: [
                      { type: 'bar', data: curva.itens.slice(0, 40).map((i) => i.faturamento_atual),
                        itemStyle: { color: cor.wine } },
                      { type: 'line', yAxisIndex: 1,
                        data: curva.itens.slice(0, 40).map((i) => i.participacao_acumulada_pct),
                        lineStyle: { color: cor.pos, width: 2 }, itemStyle: { color: cor.pos },
                        symbol: 'none' },
                    ],
                  }}
                />
              </Card>

              <Card titulo="Produtos" acoes={
                <ComoFoiCalculado calculo={{
                  titulo: 'Como a curva ABC foi calculada',
                  formula: curva.calculo.formula,
                  valores: Object.entries(curva.calculo.valores ?? {}).map(([rotulo, valor]) => ({ rotulo, valor: String(valor) })),
                  premissas: curva.calculo.premissas,
                }} />
              }>
                <div className="rolagem">
                  <table>
                    <thead>
                      <tr>
                        <Th campo="produto" ordem={ordemCurva} alternar={alternarCurva}>Produto</Th>
                        <Th campo="classe_abc" ordem={ordemCurva} alternar={alternarCurva}>Classe</Th>
                        <Th campo="faturamento_atual" ordem={ordemCurva} alternar={alternarCurva} num>Faturamento</Th>
                        <Th campo="participacao_pct" ordem={ordemCurva} alternar={alternarCurva} num>Participação</Th>
                        <Th campo="participacao_acumulada_pct" ordem={ordemCurva} alternar={alternarCurva} num>Acumulado</Th>
                        <Th campo="unidades_atual" ordem={ordemCurva} alternar={alternarCurva} num>Unidades</Th>
                        <Th campo="variacao_pct" ordem={ordemCurva} alternar={alternarCurva} num>Variação</Th>
                        {curva.itens[0]?.pdvs_compradores !== undefined && (
                          <Th campo="pdvs_compradores" ordem={ordemCurva} alternar={alternarCurva} num>PDVs</Th>
                        )}
                        {temShare && (
                          <th
                            className="num"
                            title="Quanto da venda Vitamedic deste produto na região passa por este cliente (base IQVIA)"
                          >
                            Share
                          </th>
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {itensCurva.map((it) => (
                        <tr key={it.produto_id}>
                          <td>{it.produto}</td>
                          <td><Tag tipo={CLASSE_TAG[it.classe_abc]}>{it.classe_abc}</Tag></td>
                          <td className="num">{brl(it.faturamento_atual)}</td>
                          <td className="num">{it.participacao_pct != null ? pct(it.participacao_pct) : '—'}</td>
                          <td className="num">{pct(it.participacao_acumulada_pct)}</td>
                          <td className="num">{inteiro(it.unidades_atual)}</td>
                          <td className={`num ${it.variacao_pct == null ? '' : it.variacao_pct >= 0 ? 'pos' : 'neg'}`}>
                            {it.variacao_pct == null ? 'novo' : `${it.variacao_pct >= 0 ? '+' : ''}${pct(it.variacao_pct)}`}
                          </td>
                          {it.pdvs_compradores !== undefined && <td className="num">{it.pdvs_compradores}</td>}
                          {temShare && (
                            <td className="num">
                              {sharePorProduto.get(it.produto_id) != null
                                ? pct(sharePorProduto.get(it.produto_id)!)
                                : '—'}
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </>
          )}

          <ComparativoMercado dados={vsMercado} />

          {matriz?.disponivel && (
            <Card titulo="ABC × Crescimento">
              {!matriz.comparacao_valida && (
                <Aviso tipo="atencao">
                  Sem período de comparação válido — todo produto aparece como "sem histórico".
                </Aviso>
              )}
              <table>
                <thead>
                  <tr><th>Classe</th><th className="num">Crescendo</th><th className="num">Estável</th><th className="num">Caindo</th></tr>
                </thead>
                <tbody>
                  {(['A', 'B', 'C'] as const).map((c) => (
                    <tr key={c}>
                      <td>{FAIXA_EMOJI[c]} {c}</td>
                      <td className="num pos">{matriz.contagem[c].CRESCENDO + matriz.contagem[c].NOVO}</td>
                      <td className="num">{matriz.contagem[c].ESTAVEL}</td>
                      <td className="num neg">{matriz.contagem[c].CAINDO}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="mut" style={{ fontSize: 11.5, marginTop: 10 }}>
                {Object.values(FAIXA_ROTULO).join(' · ')}
              </div>
            </Card>
          )}
        </div>
      )}
    </>
  )
}
