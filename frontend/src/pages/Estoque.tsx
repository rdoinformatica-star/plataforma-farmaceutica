import { useQuery } from '@tanstack/react-query'
import { Boxes, LineChart, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { ComoFoiCalculado } from '../components/ComoFoiCalculado'
import { Grafico, useCoresGrafico } from '../components/Grafico'
import { Th, useOrdenacao } from '../components/Tabela'
import { SeletorPeriodo } from '../components/dashboard/SeletorPeriodo'
import { Aviso, Card, Kpi, Tag, Vazio } from '../components/ui'
import { analytics } from '../lib/analytics'
import { api, type Cliente } from '../lib/api'
import { brl, inteiro, pct } from '../lib/format'
import { useEstado } from '../lib/estado'
import type { Periodo } from '../lib/periodo'
import { resolverPreset } from '../lib/periodo'

const CLASSE_TAG: Record<string, string> = {
  SAUDAVEL: 't-ok',
  ATENCAO: 't-hip',
  ALTO: 't-hip',
  CRITICO: 't-erro',
  ZUMBI: 't-erro',
  INDEFINIDO: 't-neutro',
}

const QUADRANTE_ROTULO: Record<string, string> = {
  RUPTURA_POTENCIAL: 'Alta venda + baixo estoque',
  CAPITAL_CONCENTRADO: 'Alta venda + alto estoque',
  EXCESSO: 'Baixa venda + alto estoque',
  BAIXA_PRIORIDADE: 'Baixa venda + baixo estoque',
}

const OBJETIVOS = [30, 60, 90, 120]

function dias(v: number | null): string {
  if (v === null) return '—'
  return `${Math.round(v).toLocaleString('pt-BR')} d`
}

export function Estoque() {
  const { clienteAtual, setClienteAtual } = useEstado()
  const { data: clientes } = useQuery({
    queryKey: ['clientes', 'ativos'],
    queryFn: () => api.get<Cliente[]>('/clientes?ativo=true'),
  })

  if (!clienteAtual) {
    return (
      <>
        <header>
          <h1>Estoque</h1>
          <p className="dek">Escolha um cliente para ver cobertura, DDE e capital parado.</p>
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
  return <EstoqueCliente clienteId={clienteAtual} clientes={clientes ?? []} />
}

function EstoqueCliente({ clienteId, clientes }: { clienteId: number; clientes: Cliente[] }) {
  const { setClienteAtual } = useEstado()
  const cor = useCoresGrafico()
  const { data: disp, isLoading: carregandoDisp } = useQuery({
    queryKey: ['analytics', 'disponibilidade', clienteId],
    queryFn: () => analytics.disponibilidade(clienteId),
  })
  const { data: perfil } = useQuery({
    queryKey: ['analytics', 'estoque-perfil', clienteId],
    queryFn: () => analytics.estoquePerfil(clienteId),
  })

  const disponivel: Periodo | null = disp?.periodo_min
    ? { ini: disp.periodo_min, fim: disp.periodo_max! }
    : null
  const [periodo, setPeriodo] = useState<Periodo | null>(null)
  useEffect(() => {
    if (disponivel && !periodo) setPeriodo(resolverPreset('semestre', disponivel))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disponivel?.ini, disponivel?.fim])

  const [base, setBase] = useState<'fonte' | 'periodo'>('fonte')
  const [filial, setFilial] = useState<string | undefined>(undefined)
  const [objetivo, setObjetivo] = useState(60)
  // Filtro de classe da tabela de posicao. Clicar na faixa (grafico ou tabela
  // de distribuicao) joga a classe aqui; clicar de novo na mesma limpa.
  const [classe, setClasse] = useState<string | null>(null)

  const p = periodo
  const temEstoque = perfil?.disponivel === true
  const habilitado = !!p && temEstoque
  const chave = [clienteId, p?.ini, p?.fim, base, filial ?? '']

  const { data: resumo } = useQuery({
    queryKey: ['analytics', 'estoque-resumo', ...chave],
    queryFn: () => analytics.estoqueResumo(clienteId, p!.ini, p!.fim, base, filial),
    enabled: habilitado,
  })
  const { data: capital } = useQuery({
    queryKey: ['analytics', 'estoque-capital', ...chave],
    queryFn: () => analytics.estoqueCapital(clienteId, p!.ini, p!.fim, base, filial),
    enabled: habilitado,
  })
  const { data: zumbi } = useQuery({
    queryKey: ['analytics', 'estoque-zumbi', ...chave],
    queryFn: () => analytics.estoqueZumbi(clienteId, p!.ini, p!.fim, 365, base, filial),
    enabled: habilitado,
  })
  const { data: matriz } = useQuery({
    queryKey: ['analytics', 'estoque-matriz', ...chave],
    queryFn: () => analytics.estoqueMatriz(clienteId, p!.ini, p!.fim, base, filial),
    enabled: habilitado,
  })
  const { data: sim } = useQuery({
    queryKey: ['analytics', 'estoque-sim', ...chave, objetivo],
    queryFn: () => analytics.estoqueSimulador(clienteId, p!.ini, p!.fim, objetivo, base, filial),
    enabled: habilitado,
  })
  const { data: posicao } = useQuery({
    queryKey: ['analytics', 'estoque-posicao', ...chave, classe ?? ''],
    queryFn: () => analytics.estoque(clienteId, p!.ini, p!.fim, base, filial, 300, classe ?? undefined),
    enabled: habilitado,
  })

  // Clicar na faixa ja selecionada limpa o filtro — evita ficar preso numa
  // classe sem um botao separado de "limpar".
  const alternarClasse = (nome: string) =>
    setClasse((atual) => (atual === nome ? null : nome || null))

  const { itens: itensSim, ordem: ordemSim, alternar: alternarSim } = useOrdenacao(
    sim?.disponivel ? sim.itens.slice(0, 25) : [],
  )
  const { itens: itensZumbi, ordem: ordemZumbi, alternar: alternarZumbi } = useOrdenacao(
    zumbi?.disponivel ? zumbi.itens.slice(0, 25) : [],
  )
  const { itens: itensPosicao, ordem: ordemPos, alternar: alternarPos } = useOrdenacao(
    posicao?.disponivel ? posicao.itens : [],
  )

  if (carregandoDisp || !disp) return <Card><div className="mut">Carregando...</div></Card>

  const filiais = perfil?.disponivel ? perfil.por_filial : []

  return (
    <>
      <header>
        <div className="linha entre">
          <div>
            <h1>Estoque — {disp.cliente}</h1>
            <p className="dek">Cobertura em dias, capital parado e o que dá para liberar.</p>
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

      {perfil && !perfil.disponivel ? (
        <Card>
          <Vazio
            icone={<Boxes size={36} />}
            titulo="Este cliente ainda não possui estoque importado."
            acao={<Link to="/importar" className="btn primario">Importar estoque</Link>}
          >
            {perfil.motivo}
          </Vazio>
        </Card>
      ) : !disp.tem_sellout ? (
        <Card>
          <Vazio
            icone={<LineChart size={36} />}
            titulo="Sem sell-out, não dá para medir velocidade de venda."
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

          {perfil?.disponivel && (
            <Card
              titulo="Origem do estoque"
              acoes={
                <ComoFoiCalculado
                  calculo={{
                    titulo: 'Como o perfil foi lido',
                    formula: perfil.calculo.formula,
                    valores: Object.entries(perfil.calculo.valores ?? {}).map(([rotulo, valor]) => ({
                      rotulo,
                      valor: String(valor),
                    })),
                    premissas: perfil.calculo.premissas,
                  }}
                />
              }
            >
              <div className="pilha" style={{ gap: 10 }}>
                <div className="linha" style={{ gap: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                  <label style={{ width: 190, marginBottom: 0 }}>
                    <span>Filial</span>
                    <select value={filial ?? ''} onChange={(e) => setFilial(e.target.value || undefined)}>
                      <option value="">Todas</option>
                      {filiais.map((f) => (
                        <option key={f.filial} value={f.filial}>
                          {f.filial}{f.tem_posicao_fisica ? '' : ' (sem posição)'}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label style={{ width: 230, marginBottom: 0 }}>
                    <span>Velocidade de venda</span>
                    <select value={base} onChange={(e) => setBase(e.target.value as 'fonte' | 'periodo')}>
                      <option value="fonte">Média do arquivo de estoque</option>
                      <option value="periodo">Sell-out do período selecionado</option>
                    </select>
                  </label>
                  <div className="mut" style={{ fontSize: 12 }}>
                    Foto de <b>{perfil.data_ref}</b> · {inteiro(perfil.produtos)} produtos
                  </div>
                </div>

                <table>
                  <thead>
                    <tr>
                      <th>Filial</th>
                      <th className="num">Linhas</th>
                      <th className="num">Com posição física</th>
                      <th className="num">Com valor</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {filiais.map((f) => (
                      <tr key={f.filial}>
                        <td style={{ fontWeight: 600 }}>{f.filial}</td>
                        <td className="num">{inteiro(f.linhas)}</td>
                        <td className="num">{inteiro(f.com_posicao)}</td>
                        <td className="num">{inteiro(f.com_valor)}</td>
                        <td>
                          {f.tem_posicao_fisica ? (
                            <Tag tipo="t-ok">posição física</Tag>
                          ) : (
                            <Tag tipo="t-neutro">só média de venda</Tag>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {filiais.some((f) => !f.tem_posicao_fisica) && (
                  <Aviso tipo="info">
                    Uma das filiais veio sem posição física no arquivo — só com média de
                    venda. Essas linhas ficam fora de DDE e capital parado, em vez de
                    entrarem como estoque zero.
                  </Aviso>
                )}
              </div>
            </Card>
          )}

          {resumo?.disponivel && (
            <>
              <div className="kpis">
                <Kpi rotulo="Estoque total" valor={brl(resumo.valor_total)} />
                <Kpi rotulo="SKUs com estoque" valor={inteiro(resumo.skus_com_estoque)} />
                <Kpi
                  rotulo="Cobertura média"
                  valor={dias(resumo.cobertura_media_dias)}
                  sub={`ponderada por valor: ${dias(resumo.cobertura_ponderada_dias)}`}
                />
                <Kpi
                  rotulo="Estoque > 180 dias"
                  valor={brl(resumo.valor_acima_180)}
                  sub={`${resumo.skus_acima_180} SKUs`}
                />
                <Kpi
                  rotulo="Estoque > 365 dias"
                  valor={brl(resumo.valor_acima_365)}
                  sub={`${resumo.skus_acima_365} SKUs`}
                />
                <Kpi
                  rotulo="Capital parado (>180d)"
                  valor={capital?.disponivel ? brl(capital.faixas[0]?.valor ?? 0) : '—'}
                  sub={
                    capital?.disponivel && capital.faixas[0]?.pct_do_estoque !== null
                      ? `${pct(capital.faixas[0]!.pct_do_estoque)} do estoque`
                      : undefined
                  }
                />
              </div>

              <Card
                titulo="Distribuição por faixa de cobertura"
                acoes={
                  <ComoFoiCalculado
                    calculo={{
                      titulo: 'Como as faixas foram calculadas',
                      formula: resumo.calculo.formula,
                      valores: Object.entries(resumo.calculo.valores ?? {}).map(([rotulo, valor]) => ({
                        rotulo,
                        valor: String(valor),
                      })),
                      premissas: resumo.calculo.premissas,
                    }}
                  />
                }
              >
                <div className="mut" style={{ fontSize: 12 }}>
                  Clique numa faixa (na barra ou na linha) para filtrar a tabela
                  de SKUs no fim da página.
                </div>
                <Grafico
                  aoClicar={(nome) => alternarClasse(nome)}
                  opcoes={{
                    xAxis: {
                      type: 'category',
                      data: resumo.por_classe.map((c) => c.classe),
                      axisLine: { lineStyle: { color: cor.borderForte } },
                      axisLabel: { color: cor.muted },
                    },
                    yAxis: {
                      type: 'value',
                      axisLabel: { color: cor.muted },
                      splitLine: { lineStyle: { color: cor.border } },
                    },
                    series: [
                      {
                        type: 'bar',
                        data: resumo.por_classe.map((c) => ({
                          value: c.valor,
                          itemStyle: {
                            color: classe && classe !== c.classe ? cor.border : cor.wine,
                          },
                        })),
                      },
                    ],
                  }}
                />
                <table>
                  <thead>
                    <tr>
                      <th>Faixa</th>
                      <th className="num">SKUs</th>
                      <th className="num">Valor em estoque</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resumo.por_classe.map((c) => (
                      <tr
                        key={c.classe}
                        onClick={() => alternarClasse(c.classe)}
                        style={{
                          cursor: 'pointer',
                          background: classe === c.classe ? 'var(--sel, rgba(127,29,29,.08))' : undefined,
                        }}
                      >
                        <td><Tag tipo={CLASSE_TAG[c.classe] ?? 't-neutro'}>{c.classe}</Tag></td>
                        <td className="num">{inteiro(c.skus)}</td>
                        <td className="num">{brl(c.valor)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {resumo.skus_dde_indefinido > 0 && (
                  <Aviso tipo="info">
                    {resumo.skus_dde_indefinido} SKU(s) com devolução líquida maior que a
                    venda ficaram como INDEFINIDO: a cobertura deles não é interpretável
                    (a própria fonte devolve dias negativos), então ficam fora das faixas.
                  </Aviso>
                )}
              </Card>
            </>
          )}

          <Card
            titulo="Simulador de estoque"
            acoes={
              sim?.disponivel ? (
                <ComoFoiCalculado
                  calculo={{
                    titulo: 'Como a simulação foi feita',
                    formula: sim.calculo.formula,
                    valores: Object.entries(sim.calculo.valores ?? {}).map(([rotulo, valor]) => ({
                      rotulo,
                      valor: String(valor),
                    })),
                    premissas: sim.calculo.premissas,
                  }}
                />
              ) : undefined
            }
          >
            <div className="pilha" style={{ gap: 10 }}>
              <div className="linha" style={{ gap: 8, flexWrap: 'wrap' }}>
                {OBJETIVOS.map((o) => (
                  <button
                    key={o}
                    className={objetivo === o ? 'primario' : ''}
                    onClick={() => setObjetivo(o)}
                  >
                    {o} dias
                  </button>
                ))}
                <label style={{ width: 150, marginBottom: 0 }}>
                  <span>Personalizado</span>
                  <input
                    type="number"
                    min={1}
                    value={objetivo}
                    onChange={(e) => setObjetivo(Math.max(1, Number(e.target.value)))}
                  />
                </label>
              </div>

              {sim?.disponivel ? (
                <>
                  <div className="mut" style={{ fontSize: 13 }}>
                    O simulador compara o estoque de cada SKU com quanto ele{' '}
                    <b>precisaria</b> ter para cobrir só os {sim.objetivo_dias} dias de
                    objetivo, no ritmo de venda atual. O que sobra disso é o{' '}
                    <b>excesso</b>; multiplicando o excesso pelo valor unitário do
                    estoque, chega-se ao <b>capital potencialmente liberável</b> — o
                    dinheiro que está parado além do necessário para aquele objetivo de
                    cobertura.
                  </div>
                  <div className="kpis">
                    <Kpi rotulo="Estoque atual" valor={brl(sim.valor_estoque_atual)} sub="valor de todo o estoque em SKUs" />
                    <Kpi rotulo="Objetivo" valor={`${sim.objetivo_dias} dias`} sub="cobertura desejada" />
                    <Kpi
                      rotulo="Capital potencialmente liberável"
                      valor={brl(sim.capital_potencialmente_liberavel)}
                      sub={
                        sim.pct_do_estoque !== null
                          ? `${pct(sim.pct_do_estoque)} do estoque está acima do objetivo`
                          : undefined
                      }
                    />
                    <Kpi rotulo="SKUs com excesso" valor={inteiro(sim.n_skus_com_excesso)} sub="têm mais estoque do que o objetivo pede" />
                  </div>
                  <Aviso tipo="atencao">
                    <b>POTENCIALMENTE LIBERÁVEL — não é dinheiro garantidamente
                    recuperável.</b> É o valor do excesso de estoque, não um valor em
                    caixa: para virar dinheiro de verdade, esse excesso precisa ser
                    vendido (no ritmo medido, sem sazonalidade) ou devolvido ao
                    fornecedor. A premissa é que a venda futura segue o ritmo medido;
                    não entram lote mínimo, validade nem acordo de recompra, que não
                    estão na base.
                  </Aviso>
                  <div className="rolagem">
                    <table>
                      <thead>
                        <tr>
                          <Th campo="produto" ordem={ordemSim} alternar={alternarSim}>Produto</Th>
                          <Th campo="filial" ordem={ordemSim} alternar={alternarSim}>Filial</Th>
                          <Th campo="estoque_atual_un" ordem={ordemSim} alternar={alternarSim} num titulo="Estoque disponível hoje, em unidades">Estoque atual</Th>
                          <Th campo="estoque_objetivo_un" ordem={ordemSim} alternar={alternarSim} num titulo="Unidades necessárias para cobrir o objetivo de dias, no ritmo de venda atual">Objetivo</Th>
                          <Th campo="excesso_un" ordem={ordemSim} alternar={alternarSim} num titulo="Estoque atual menos o objetivo, em unidades">Excesso</Th>
                          <Th campo="excesso_valor" ordem={ordemSim} alternar={alternarSim} num titulo="Excesso em unidades × valor unitário do estoque — o capital parado além do objetivo">Capital do excesso</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {itensSim.map((i) => (
                          <tr key={`${i.produto_id}-${i.filial}`}>
                            <td>
                              {i.produto}
                              {i.sem_giro && <> <Tag tipo="t-erro">sem giro</Tag></>}
                            </td>
                            <td>{i.filial}</td>
                            <td className="num">{inteiro(i.estoque_atual_un)}</td>
                            <td className="num">{inteiro(Math.round(i.estoque_objetivo_un))}</td>
                            <td className="num">{inteiro(Math.round(i.excesso_un))}</td>
                            <td className="num" style={{ fontWeight: 600 }}>{brl(i.excesso_valor)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              ) : (
                <div className="mut">{sim?.motivo ?? 'Carregando...'}</div>
              )}
            </div>
          </Card>

          <Card
            titulo="Estoque × vendas"
            acoes={
              matriz?.disponivel ? (
                <ComoFoiCalculado
                  calculo={{
                    titulo: 'Como os quadrantes foram definidos',
                    formula: matriz.calculo.formula,
                    valores: Object.entries(matriz.calculo.valores ?? {}).map(([rotulo, valor]) => ({
                      rotulo,
                      valor: String(valor),
                    })),
                    premissas: matriz.calculo.premissas,
                  }}
                />
              ) : undefined
            }
          >
            {matriz?.disponivel ? (
              <div className="pilha" style={{ gap: 10 }}>
                <div className="grade c2">
                  {matriz.quadrantes.map((qd) => (
                    <div key={qd.quadrante} className="claim fato" style={{ margin: 0 }}>
                      <div className="linha entre">
                        <b>{QUADRANTE_ROTULO[qd.quadrante] ?? qd.quadrante}</b>
                        <span className="num" style={{ fontWeight: 700 }}>{qd.skus}</span>
                      </div>
                      <div className="mut" style={{ fontSize: 12, marginTop: 4 }}>{qd.descricao}</div>
                      <div className="mut" style={{ fontSize: 12, marginTop: 6 }}>
                        estoque {brl(qd.valor_estoque)} · venda {brl(qd.faturamento)}
                      </div>
                    </div>
                  ))}
                </div>
                <Aviso tipo="info">
                  “Risco de ruptura” aqui é um alerta a verificar, não uma previsão: os
                  dados mostram cobertura baixa com venda alta, mas não mostram pedido em
                  trânsito nem prazo de reposição.
                </Aviso>
              </div>
            ) : (
              <div className="mut">{matriz?.motivo ?? 'Carregando...'}</div>
            )}
          </Card>

          <Card titulo="Estoque zumbi (acima de 365 dias)">
            {zumbi?.disponivel ? (
              zumbi.itens.length === 0 ? (
                <Vazio icone={null} titulo="Nenhum SKU acima do limite. " />
              ) : (
                <div className="pilha" style={{ gap: 8 }}>
                  <div className="linha" style={{ gap: 16 }}>
                    <Kpi rotulo="SKUs" valor={inteiro(zumbi.n_skus)} />
                    <Kpi rotulo="Capital imobilizado" valor={brl(zumbi.valor_total)} />
                  </div>
                  <div className="rolagem">
                    <table>
                      <thead>
                        <tr>
                          <Th campo="produto" ordem={ordemZumbi} alternar={alternarZumbi}>Produto</Th>
                          <Th campo="filial" ordem={ordemZumbi} alternar={alternarZumbi}>Filial</Th>
                          <Th campo="estoque_disp_un" ordem={ordemZumbi} alternar={alternarZumbi} num>Estoque</Th>
                          <Th campo="media_venda_mes_fonte" ordem={ordemZumbi} alternar={alternarZumbi} num>Venda média/mês</Th>
                          <Th campo="dde" ordem={ordemZumbi} alternar={alternarZumbi} num>DDE</Th>
                          <Th campo="valor_estoque" ordem={ordemZumbi} alternar={alternarZumbi} num>Valor</Th>
                          <Th campo="classificacao" ordem={ordemZumbi} alternar={alternarZumbi}>Classe</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {itensZumbi.map((i) => (
                          <tr key={`${i.produto_id}-${i.filial}`}>
                            <td>
                              🔴 {i.produto}
                            </td>
                            <td>{i.filial}</td>
                            <td className="num">{inteiro(i.estoque_disp_un)}</td>
                            <td className="num">
                              {i.media_venda_mes_fonte === null ? '—' : inteiro(i.media_venda_mes_fonte)}
                            </td>
                            <td className="num">{i.dde === null ? 'sem venda' : dias(i.dde)}</td>
                            <td className="num">{brl(i.valor_estoque)}</td>
                            <td><Tag tipo={CLASSE_TAG[i.classificacao] ?? 't-neutro'}>{i.classificacao}</Tag></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )
            ) : (
              <div className="mut">{zumbi?.motivo ?? 'Carregando...'}</div>
            )}
          </Card>

          <Card
            titulo="Posição de estoque por SKU"
            acoes={
              <div className="linha" style={{ gap: 8, alignItems: 'center' }}>
                <select
                  value={classe ?? ''}
                  onChange={(e) => setClasse(e.target.value || null)}
                  style={{ width: 150 }}
                  title="Filtrar por faixa de cobertura"
                >
                  <option value="">Todas as classes</option>
                  {(posicao?.disponivel ? posicao.faixas.map((f) => f.rotulo) : []).map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                  <option value="INDEFINIDO">INDEFINIDO</option>
                </select>
                {posicao?.disponivel ? (
                  <ComoFoiCalculado
                    calculo={{
                      titulo: 'Como o DDE foi calculado',
                      formula: posicao.calculo.formula,
                      valores: Object.entries(posicao.calculo.valores ?? {}).map(([rotulo, valor]) => ({
                        rotulo,
                        valor: String(valor),
                      })),
                      premissas: posicao.calculo.premissas,
                    }}
                  />
                ) : null}
              </div>
            }
          >
            {posicao?.disponivel ? (
              <div className="pilha" style={{ gap: 8 }}>
                {classe && (
                  <div className="linha" style={{ gap: 8, alignItems: 'center' }}>
                    <Tag tipo={CLASSE_TAG[classe] ?? 't-neutro'}>{classe}</Tag>
                    <span className="mut" style={{ fontSize: 12 }}>
                      {inteiro(posicao.itens.length)} de {inteiro(posicao.n_total_sem_filtro)} SKUs
                    </span>
                    <button className="discreto" onClick={() => setClasse(null)}>
                      limpar filtro
                    </button>
                  </div>
                )}
                <div className="rolagem">
                <table>
                  <thead>
                    <tr>
                      <Th campo="produto" ordem={ordemPos} alternar={alternarPos}>Produto</Th>
                      <Th campo="filial" ordem={ordemPos} alternar={alternarPos}>Filial</Th>
                      <Th campo="estoque_disp_un" ordem={ordemPos} alternar={alternarPos} num>Estoque</Th>
                      <Th campo="media_venda_mes_fonte" ordem={ordemPos} alternar={alternarPos} num>Venda média/mês</Th>
                      <Th campo="dde_fonte" ordem={ordemPos} alternar={alternarPos} num>DDE (fonte)</Th>
                      <Th campo="dde_periodo" ordem={ordemPos} alternar={alternarPos} num>DDE (período)</Th>
                      <Th campo="valor_estoque" ordem={ordemPos} alternar={alternarPos} num>Valor</Th>
                      <Th campo="classificacao" ordem={ordemPos} alternar={alternarPos}>Classe</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {itensPosicao.map((i) => (
                      <tr key={`${i.produto_id}-${i.filial}`}>
                        <td>{i.produto}</td>
                        <td>{i.filial}</td>
                        <td className="num">{inteiro(i.estoque_disp_un)}</td>
                        <td className="num">
                          {i.media_venda_mes_fonte === null ? '—' : inteiro(i.media_venda_mes_fonte)}
                        </td>
                        <td className="num">{dias(i.dde_fonte)}</td>
                        <td className="num">{dias(i.dde_periodo)}</td>
                        <td className="num">{brl(i.valor_estoque)}</td>
                        <td><Tag tipo={CLASSE_TAG[i.classificacao] ?? 't-neutro'}>{i.classificacao}</Tag></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
                {posicao.itens.length === 0 && (
                  <div className="mut" style={{ fontSize: 13 }}>
                    Nenhum SKU nesta faixa.
                  </div>
                )}
              </div>
            ) : (
              <div className="mut">{posicao?.motivo ?? 'Carregando...'}</div>
            )}
          </Card>
        </div>
      )}
    </>
  )
}
