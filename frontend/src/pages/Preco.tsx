import { useQuery } from '@tanstack/react-query'
import { Tag as TagIcon, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { ComoFoiCalculado } from '../components/ComoFoiCalculado'
import { Grafico, useCoresGrafico } from '../components/Grafico'
import { Th, useOrdenacao } from '../components/Tabela'
import { SeletorPeriodo } from '../components/dashboard/SeletorPeriodo'
import { Aviso, Card, Kpi, Tag, Vazio } from '../components/ui'
import { analytics, type Calculo } from '../lib/analytics'
import { api, type Cliente } from '../lib/api'
import { inteiro, pct } from '../lib/format'
import { useEstado } from '../lib/estado'
import type { Periodo } from '../lib/periodo'
import { resolverPreset } from '../lib/periodo'

const POSICAO_TAG: Record<string, string> = {
  ACIMA: 't-erro',
  ABAIXO: 't-ok',
  EM_LINHA: 't-neutro',
}

const POSICAO_ROTULO: Record<string, string> = {
  ACIMA: 'acima do mercado',
  ABAIXO: 'abaixo do mercado',
  EM_LINHA: 'em linha',
}

function comoCalculado(titulo: string, c: Calculo) {
  return (
    <ComoFoiCalculado
      calculo={{
        titulo,
        formula: c.formula,
        valores: Object.entries(c.valores ?? {}).map(([rotulo, valor]) => ({
          rotulo,
          valor: String(valor),
        })),
        premissas: c.premissas,
      }}
    />
  )
}

const rs = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `R$ ${v.toFixed(2).replace('.', ',')}`

export function Preco() {
  const { clienteAtual, setClienteAtual } = useEstado()
  const { data: clientes } = useQuery({
    queryKey: ['clientes', 'ativos'],
    queryFn: () => api.get<Cliente[]>('/clientes?ativo=true'),
  })

  if (!clienteAtual) {
    return (
      <>
        <header>
          <h1>Preço</h1>
          <p className="dek">Escolha um cliente para comparar preço com os demais distribuidores.</p>
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
  return <PrecoCliente clienteId={clienteAtual} clientes={clientes ?? []} />
}

function PrecoCliente({ clienteId, clientes }: { clienteId: number; clientes: Cliente[] }) {
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

  const [uf, setUf] = useState<string | undefined>(undefined)
  const [minimo, setMinimo] = useState(200)
  const p = periodo
  const habilitado = !!p

  const { data: comp } = useQuery({
    queryKey: ['analytics', 'preco-comparabilidade', clienteId],
    queryFn: () => analytics.precoComparabilidade(clienteId),
  })
  const { data: preco } = useQuery({
    queryKey: ['analytics', 'preco', clienteId, p?.ini, p?.fim, uf ?? '', minimo],
    queryFn: () => analytics.preco(clienteId, p!.ini, p!.fim, uf, minimo),
    enabled: habilitado,
  })
  const { data: evol } = useQuery({
    queryKey: ['analytics', 'preco-evolucao', clienteId, p?.ini, p?.fim, uf ?? ''],
    queryFn: () => analytics.precoEvolucao(clienteId, p!.ini, p!.fim, undefined, uf),
    enabled: habilitado,
  })
  const { data: varejo } = useQuery({
    queryKey: ['analytics', 'preco-varejo', clienteId, uf ?? ''],
    queryFn: () => analytics.precoVarejo(clienteId, uf),
  })
  const { data: ufs } = useQuery({
    queryKey: ['analytics', 'uf', clienteId, p?.ini, p?.fim],
    queryFn: () => analytics.uf(clienteId, p!.ini, p!.fim),
    enabled: habilitado,
  })

  const { itens: itensPreco, ordem: ordemPreco, alternar: alternarPreco } = useOrdenacao(
    preco?.disponivel ? preco.itens.slice(0, 30) : [],
  )
  const { itens: itensVarejo, ordem: ordemVarejo, alternar: alternarVarejo } = useOrdenacao(
    varejo?.disponivel ? varejo.itens.slice(0, 20) : [],
  )

  if (carregandoDisp || !disp) return <Card><div className="mut">Carregando...</div></Card>

  const listaUf = ufs?.disponivel ? ufs.itens.map((i) => i.uf) : []

  return (
    <>
      <header>
        <div className="linha entre">
          <div>
            <h1>Preço — {disp.cliente}</h1>
            <p className="dek">Preço praticado ao PDV, contra os demais distribuidores.</p>
          </div>
          <select
            value={clienteId}
            onChange={(e) => setClienteAtual(Number(e.target.value))}
            style={{ width: 200 }}
          >
            {clientes.map((c) => (
              <option key={c.id} value={c.id}>{c.nome}</option>
            ))}
          </select>
        </div>
      </header>

      {!disp.tem_sellout ? (
        <Card>
          <Vazio
            icone={<TagIcon size={36} />}
            titulo="Sem sell-out importado, não há preço para calcular."
            acao={<Link to="/importar" className="btn primario">Importar um relatório</Link>}
          >
            {disp.motivo_indisponivel}
          </Vazio>
        </Card>
      ) : (
        <div className="pilha">
          {disponivel && (
            <SeletorPeriodo disponivel={disponivel} valor={periodo ?? disponivel} aoMudar={setPeriodo} />
          )}

          <Card
            titulo="O que pode ser comparado com o quê"
            acoes={comp?.disponivel ? comoCalculado('Como a comparabilidade foi decidida', comp.calculo) : undefined}
          >
            {comp?.disponivel ? (
              <div className="pilha" style={{ gap: 10 }}>
                <table>
                  <thead>
                    <tr>
                      <th>Fonte</th>
                      <th>Elo da cadeia</th>
                      <th>Período</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {comp.fontes.map((f) => (
                      <tr key={f.fonte}>
                        <td style={{ fontWeight: 600 }}>{f.fonte}</td>
                        <td>{f.elo}</td>
                        <td className="mut">{f.periodo}</td>
                        <td>
                          <Tag tipo={f.disponivel ? 't-ok' : 't-neutro'}>
                            {f.disponivel ? 'disponível' : 'indisponível'}
                          </Tag>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div className="pilha" style={{ gap: 8 }}>
                  {comp.pares.map((par, i) => (
                    <div key={i} className="claim fato" style={{ margin: 0 }}>
                      <div className="linha" style={{ gap: 8 }}>
                        <Tag tipo={par.comparavel ? 't-ok' : 't-erro'}>
                          {par.comparavel ? 'comparável' : 'não comparável'}
                        </Tag>
                        <span style={{ fontWeight: 600 }}>
                          {par.de} × {par.para}
                        </span>
                      </div>
                      <div className="mut" style={{ fontSize: 12, marginTop: 6 }}>{par.motivo}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="mut">Carregando...</div>
            )}
          </Card>

          <div className="linha" style={{ gap: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <label style={{ width: 170, marginBottom: 0 }}>
              <span>Praça (UF)</span>
              <select value={uf ?? ''} onChange={(e) => setUf(e.target.value || undefined)}>
                <option value="">Todas</option>
                {listaUf.map((u) => (
                  <option key={u} value={u}>{u}</option>
                ))}
              </select>
            </label>
            <label style={{ width: 200, marginBottom: 0 }}>
              <span>Volume mínimo (unidades)</span>
              <input
                type="number"
                min={0}
                step={50}
                value={minimo}
                onChange={(e) => setMinimo(Math.max(0, Number(e.target.value)))}
              />
            </label>
          </div>

          {preco?.disponivel && (
            <>
              <div className="kpis">
                <Kpi rotulo="Preço médio do cliente" valor={rs(preco.preco_medio_cliente)} />
                <Kpi rotulo="Preço médio dos demais" valor={rs(preco.preco_medio_outros)} />
                <Kpi rotulo="SKUs comparáveis" valor={inteiro(preco.n_comparaveis)} />
                <Kpi
                  rotulo="Fora por volume"
                  valor={inteiro(preco.n_sem_volume)}
                  sub={`abaixo de ${preco.minimo_unidades} un`}
                />
              </div>

              <Card
                titulo="Preço por SKU — cliente × demais distribuidores"
                acoes={comoCalculado('Como o preço foi calculado', preco.calculo)}
              >
                <div className="rolagem">
                  <table>
                    <thead>
                      <tr>
                        <Th campo="produto" ordem={ordemPreco} alternar={alternarPreco}>Produto</Th>
                        <Th campo="preco_cliente" ordem={ordemPreco} alternar={alternarPreco} num>Preço cliente</Th>
                        <Th campo="preco_outros" ordem={ordemPreco} alternar={alternarPreco} num>Preço demais</Th>
                        <Th campo="diferenca_pct" ordem={ordemPreco} alternar={alternarPreco} num>Diferença</Th>
                        <Th campo="unidades_cliente" ordem={ordemPreco} alternar={alternarPreco} num>Unidades</Th>
                        <Th campo="posicao" ordem={ordemPreco} alternar={alternarPreco}>Posição</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {itensPreco.map((i) => (
                        <tr key={i.produto_id}>
                          <td>{i.produto}</td>
                          <td className="num">{rs(i.preco_cliente)}</td>
                          <td className="num">{rs(i.preco_outros)}</td>
                          <td className="num" style={{ fontWeight: 600 }}>
                            {i.diferenca_pct === null ? '—' : pct(i.diferenca_pct)}
                          </td>
                          <td className="num">{inteiro(i.unidades_cliente)}</td>
                          <td>
                            {i.posicao && (
                              <Tag tipo={POSICAO_TAG[i.posicao]}>{POSICAO_ROTULO[i.posicao]}</Tag>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {preco.sem_volume.length > 0 && (
                  <details style={{ marginTop: 10 }}>
                    <summary className="mut" style={{ cursor: 'pointer', fontSize: 13 }}>
                      {preco.n_sem_volume} SKU(s) fora da comparação por volume insuficiente
                    </summary>
                    <table style={{ marginTop: 8 }}>
                      <tbody>
                        {preco.sem_volume.slice(0, 15).map((s) => (
                          <tr key={s.produto_id}>
                            <td>{s.produto}</td>
                            <td className="num">{inteiro(s.unidades_cliente)} un (cliente)</td>
                            <td className="num">{inteiro(s.unidades_outros)} un (demais)</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </details>
                )}
              </Card>
            </>
          )}

          {evol?.disponivel && (
            <Card
              titulo="Evolução do preço médio do cliente"
              acoes={comoCalculado('Como a evolução foi calculada', evol.calculo)}
            >
              <Grafico
                opcoes={{
                  xAxis: {
                    type: 'category',
                    data: evol.serie.map((s) => String(s.periodo)),
                    axisLine: { lineStyle: { color: cor.borderForte } },
                    axisLabel: { color: cor.muted },
                  },
                  yAxis: {
                    type: 'value',
                    scale: true,
                    axisLabel: { color: cor.muted },
                    splitLine: { lineStyle: { color: cor.border } },
                  },
                  series: [
                    {
                      type: 'line',
                      smooth: true,
                      data: evol.serie.map((s) => s.preco_medio),
                      itemStyle: { color: cor.wine },
                      lineStyle: { color: cor.wine },
                    },
                  ],
                }}
              />
              <div className="mut" style={{ fontSize: 12 }}>
                {rs(evol.preco_inicial)} → {rs(evol.preco_final)}{' '}
                {evol.variacao_pct !== null && <b>({pct(evol.variacao_pct)})</b>}
              </div>
              <Aviso tipo="info">
                Preço médio realizado, não preço de tabela: muda com mix de produto,
                desconto e bonificação dentro do próprio mês.
              </Aviso>
            </Card>
          )}

          <Card
            titulo="Preço de varejo da indústria (IQVIA)"
            acoes={varejo?.disponivel ? comoCalculado('Como o preço de varejo foi calculado', varejo.calculo) : undefined}
          >
            {varejo?.disponivel ? (
              <div className="pilha" style={{ gap: 10 }}>
                <Aviso tipo="atencao">
                  Este bloco é <b>outro elo da cadeia</b> (PDV → consumidor) e{' '}
                  <b>não se compara</b> com os preços acima, que são do distribuidor ao
                  PDV. Está aqui como contexto competitivo da indústria, não como
                  referência de preço do cliente.
                </Aviso>
                <div className="rolagem">
                  <table>
                    <thead>
                      <tr>
                        <Th campo="mercado" ordem={ordemVarejo} alternar={alternarVarejo}>Mercado</Th>
                        <Th campo="preco_vitamedic" ordem={ordemVarejo} alternar={alternarVarejo} num>Preço VITAMEDIC</Th>
                        <Th campo="lider" ordem={ordemVarejo} alternar={alternarVarejo}>Líder</Th>
                        <Th campo="preco_lider" ordem={ordemVarejo} alternar={alternarVarejo} num>Preço líder</Th>
                        <Th campo="indice_vs_lider_pct" ordem={ordemVarejo} alternar={alternarVarejo} num>vs líder</Th>
                        <Th campo="concorrentes_mais_baratos" ordem={ordemVarejo} alternar={alternarVarejo} num>Mais baratos</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {itensVarejo.map((i) => (
                        <tr key={i.mercado}>
                          <td>{i.mercado}</td>
                          <td className="num">{rs(i.preco_vitamedic)}</td>
                          <td className="mut">{i.lider}</td>
                          <td className="num">{rs(i.preco_lider)}</td>
                          <td className="num" style={{ fontWeight: 600 }}>
                            {i.indice_vs_lider_pct === null ? '—' : pct(i.indice_vs_lider_pct)}
                          </td>
                          <td className="num">
                            {i.concorrentes_mais_baratos}/{i.concorrentes}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="mut">{varejo?.motivo ?? 'Carregando...'}</div>
            )}
          </Card>
        </div>
      )}
    </>
  )
}
