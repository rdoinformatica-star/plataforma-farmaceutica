import { useMutation, useQuery } from '@tanstack/react-query'
import { Download, ShoppingCart, Users } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { ComoFoiCalculado } from '../components/ComoFoiCalculado'
import { Th, useOrdenacao } from '../components/Tabela'
import { SeletorPeriodo } from '../components/dashboard/SeletorPeriodo'
import { Aviso, Card, Kpi, Tag, Vazio } from '../components/ui'
import { analytics, type Agrupamento, type EntradaPedido } from '../lib/analytics'
import { api, type Cliente } from '../lib/api'
import { brl, inteiro } from '../lib/format'
import { useEstado } from '../lib/estado'
import type { Periodo } from '../lib/periodo'
import { resolverPreset } from '../lib/periodo'

const AGRUPAMENTOS: { valor: Agrupamento; rotulo: string; ajuda: string }[] = [
  { valor: 'abc', rotulo: 'Curva ABC',
    ajuda: 'A/B/C pelo faturamento do próprio cliente. O corte clássico do comprador.' },
  { valor: 'estoque', rotulo: 'Faixa de cobertura',
    ajuda: 'Saudável, atenção, alto, crítico, zumbi — pela situação atual do estoque.' },
  { valor: 'marca', rotulo: 'Marca / linha',
    ajuda: 'Marca do cadastro. Mistura marca de verdade com nome de molécula.' },
]

const CLASSE_TAG: Record<string, string> = {
  SAUDAVEL: 't-ok', ATENCAO: 't-hip', ALTO: 't-hip',
  CRITICO: 't-erro', ZUMBI: 't-erro', INDEFINIDO: 't-neutro',
}

function dias(v: number | null): string {
  if (v === null) return '—'
  return `${Math.round(v).toLocaleString('pt-BR')} d`
}

export function Compra() {
  const { clienteAtual, setClienteAtual } = useEstado()
  const { data: clientes } = useQuery({
    queryKey: ['clientes', 'ativos'],
    queryFn: () => api.get<Cliente[]>('/clientes?ativo=true'),
  })

  if (!clienteAtual) {
    return (
      <>
        <header>
          <h1>Compra</h1>
          <p className="dek">Escolha um cliente para montar a sugestão de pedido.</p>
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
  return <CompraCliente clienteId={clienteAtual} clientes={clientes ?? []} />
}

function CompraCliente({ clienteId, clientes }: { clienteId: number; clientes: Cliente[] }) {
  const { setClienteAtual } = useEstado()
  const { data: disp, isLoading: carregandoDisp } = useQuery({
    queryKey: ['analytics', 'disponibilidade', clienteId],
    queryFn: () => analytics.disponibilidade(clienteId),
  })
  const { data: perfil } = useQuery({
    queryKey: ['analytics', 'estoque-perfil', clienteId],
    queryFn: () => analytics.estoquePerfil(clienteId),
  })

  const disponivel: Periodo | null = disp?.periodo_min
    ? { ini: disp.periodo_min, fim: disp.periodo_max! } : null
  const [periodo, setPeriodo] = useState<Periodo | null>(null)
  useEffect(() => {
    if (disponivel && !periodo) setPeriodo(resolverPreset('semestre', disponivel))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disponivel?.ini, disponivel?.fim])

  const [agrupamento, setAgrupamento] = useState<Agrupamento>('abc')
  const [ddePadrao, setDdePadrao] = useState(60)
  const [base, setBase] = useState<'fonte' | 'periodo'>('fonte')
  const [filial, setFilial] = useState<string | undefined>(undefined)
  const [usarAlvo, setUsarAlvo] = useState(false)
  const [valorAlvo, setValorAlvo] = useState(450000)
  const [tetoPct, setTetoPct] = useState(20)
  // DDE por grupo e por SKU ficam fora do useQuery: o comprador ajusta várias
  // linhas seguidas, e refazer a conta a cada tecla deixaria a tela travando.
  // Só entram no cálculo quando ele clica em "Recalcular".
  const [ddeGrupo, setDdeGrupo] = useState<Record<string, number>>({})
  const [ddeProduto, setDdeProduto] = useState<Record<number, number>>({})
  const [rascunhoGrupo, setRascunhoGrupo] = useState<Record<string, string>>({})
  const [rascunhoProduto, setRascunhoProduto] = useState<Record<number, string>>({})

  const p = periodo
  const temEstoque = perfil?.disponivel === true

  const entrada: EntradaPedido | null = useMemo(() => p ? {
    periodo_ini: p.ini,
    periodo_fim: p.fim,
    agrupamento,
    dde_padrao: ddePadrao,
    dde_por_grupo: ddeGrupo,
    dde_por_produto: ddeProduto,
    base_velocidade: base,
    filial: filial ?? null,
    valor_alvo: usarAlvo ? valorAlvo : null,
    teto_por_sku: tetoPct / 100,
  } : null, [p, agrupamento, ddePadrao, ddeGrupo, ddeProduto, base, filial, usarAlvo, valorAlvo, tetoPct])

  const { data: pedido, isFetching } = useQuery({
    queryKey: ['analytics', 'compra', clienteId, entrada],
    queryFn: () => analytics.compra(clienteId, entrada!),
    enabled: !!entrada && temEstoque,
  })

  const baixar = useMutation({
    mutationFn: () => analytics.compraXlsx(clienteId, entrada!),
  })

  const { itens, ordem, alternar } = useOrdenacao(
    pedido?.disponivel ? pedido.itens : [],
  )

  const aplicarGrupos = () => {
    const novo: Record<string, number> = {}
    for (const [g, v] of Object.entries(rascunhoGrupo)) {
      const n = Number(v)
      if (v !== '' && Number.isFinite(n) && n > 0) novo[g] = n
    }
    setDdeGrupo(novo)
  }
  const aplicarProdutos = () => {
    const novo: Record<number, number> = {}
    for (const [pid, v] of Object.entries(rascunhoProduto)) {
      const n = Number(v)
      if (v !== '' && Number.isFinite(n) && n > 0) novo[Number(pid)] = n
    }
    setDdeProduto(novo)
  }
  const pendenteGrupo = JSON.stringify(
    Object.fromEntries(Object.entries(rascunhoGrupo).filter(([, v]) => v !== '')),
  ) !== JSON.stringify(Object.fromEntries(Object.entries(ddeGrupo).map(([k, v]) => [k, String(v)])))
  const pendenteProduto = Object.entries(rascunhoProduto).some(
    ([pid, v]) => v !== '' && Number(v) !== ddeProduto[Number(pid)],
  )

  if (carregandoDisp || !disp) return <Card><div className="mut">Carregando...</div></Card>

  const filiais = perfil?.disponivel ? perfil.por_filial : []
  const ajudaAgrup = AGRUPAMENTOS.find((a) => a.valor === agrupamento)?.ajuda ?? ''

  return (
    <>
      <header>
        <div className="linha entre">
          <div>
            <h1>Compra — {disp.cliente}</h1>
            <p className="dek">
              Quanto comprar de cada SKU para chegar ao DDE que você definir.
            </p>
          </div>
          <select value={clienteId} onChange={(e) => setClienteAtual(Number(e.target.value))} style={{ width: 200 }}>
            {clientes.map((c) => (<option key={c.id} value={c.id}>{c.nome}</option>))}
          </select>
        </div>
      </header>

      {!temEstoque ? (
        <Card>
          <Vazio
            icone={<ShoppingCart size={36} />}
            titulo="Sem arquivo de estoque, não dá para calcular pedido."
            acao={<Link to="/importar" className="btn primario">Importar estoque</Link>}
          >
            A sugestão de compra parte da posição atual de estoque do distribuidor.
            Importe o export de estoque dele para liberar esta tela.
          </Vazio>
        </Card>
      ) : (
        <div className="pilha">
          {disponivel && <SeletorPeriodo disponivel={disponivel} valor={periodo ?? disponivel} aoMudar={setPeriodo} />}

          <Card titulo="Parâmetros do pedido">
            <div className="pilha" style={{ gap: 12 }}>
              <div className="linha" style={{ gap: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                <label style={{ width: 190, marginBottom: 0 }}>
                  <span>Agrupar por</span>
                  <select
                    value={agrupamento}
                    onChange={(e) => {
                      setAgrupamento(e.target.value as Agrupamento)
                      setDdeGrupo({})
                      setRascunhoGrupo({})
                    }}
                  >
                    {AGRUPAMENTOS.map((a) => (
                      <option key={a.valor} value={a.valor}>{a.rotulo}</option>
                    ))}
                  </select>
                </label>
                <label style={{ width: 150, marginBottom: 0 }}>
                  <span>DDE padrão (dias)</span>
                  <input
                    type="number" min={1}
                    value={ddePadrao}
                    onChange={(e) => setDdePadrao(Math.max(1, Number(e.target.value)))}
                  />
                </label>
                <label style={{ width: 200, marginBottom: 0 }}>
                  <span>Velocidade de venda</span>
                  <select value={base} onChange={(e) => setBase(e.target.value as 'fonte' | 'periodo')}>
                    <option value="fonte">Média do arquivo de estoque</option>
                    <option value="periodo">Sell-out do período</option>
                  </select>
                </label>
                <label style={{ width: 170, marginBottom: 0 }}>
                  <span>Filial</span>
                  <select value={filial ?? ''} onChange={(e) => setFilial(e.target.value || undefined)}>
                    <option value="">Todas</option>
                    {filiais.map((f) => (
                      <option key={f.filial} value={f.filial}>{f.filial}</option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="mut" style={{ fontSize: 12 }}>{ajudaAgrup}</div>

              <div className="linha" style={{ gap: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                <label style={{ marginBottom: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <input
                    type="checkbox"
                    checked={usarAlvo}
                    onChange={(e) => setUsarAlvo(e.target.checked)}
                    style={{ width: 'auto' }}
                  />
                  <span style={{ margin: 0 }}>Definir valor de compra</span>
                </label>
                {usarAlvo && (
                  <>
                    <label style={{ width: 170, marginBottom: 0 }}>
                      <span>Valor alvo (R$)</span>
                      <input
                        type="number" min={1} step={1000}
                        value={valorAlvo}
                        onChange={(e) => setValorAlvo(Math.max(1, Number(e.target.value)))}
                      />
                    </label>
                    <label style={{ width: 150, marginBottom: 0 }}>
                      <span>Teto por SKU (%)</span>
                      <input
                        type="number" min={1} max={100}
                        value={tetoPct}
                        onChange={(e) => setTetoPct(Math.min(100, Math.max(1, Number(e.target.value))))}
                      />
                    </label>
                  </>
                )}
              </div>
              {usarAlvo && (
                <Aviso tipo="info">
                  Com valor alvo, os SKUs entram por <b>urgência</b> (menor cobertura
                  primeiro) até o orçamento acabar. O teto por SKU evita que um item de
                  giro alto consuma o pedido inteiro. Se a necessidade real for menor
                  que o alvo, o sistema informa a sobra em vez de completar com o que
                  não precisa.
                </Aviso>
              )}
            </div>
          </Card>

          {pedido?.disponivel && (
            <>
              <Card
                titulo="Resumo da proposta"
                acoes={
                  <div className="linha" style={{ gap: 8, alignItems: 'center' }}>
                    <button
                      className="primario"
                      disabled={baixar.isPending || !entrada}
                      onClick={() => baixar.mutate()}
                    >
                      <Download size={14} />
                      {baixar.isPending ? 'Gerando...' : 'Baixar Excel'}
                    </button>
                    <ComoFoiCalculado
                      calculo={{
                        titulo: 'Como o pedido foi calculado',
                        formula: pedido.calculo.formula,
                        valores: Object.entries(pedido.calculo.valores ?? {}).map(([rotulo, valor]) => ({
                          rotulo, valor: String(valor),
                        })),
                        premissas: pedido.calculo.premissas,
                      }}
                    />
                  </div>
                }
              >
                <div className="pilha" style={{ gap: 10 }}>
                  {baixar.isError && (
                    <Aviso tipo="atencao">{(baixar.error as Error).message}</Aviso>
                  )}
                  <div className="kpis">
                    <Kpi rotulo="Total do pedido" valor={brl(pedido.total_valor)} />
                    <Kpi rotulo="SKUs" valor={inteiro(pedido.n_skus)} />
                    <Kpi rotulo="Unidades" valor={inteiro(pedido.total_unidades)} />
                    <Kpi
                      rotulo="Necessidade cheia"
                      valor={brl(pedido.necessidade_total)}
                      sub="sem limite de orçamento"
                    />
                  </div>

                  {pedido.corte && (
                    <Aviso tipo={pedido.corte.necessidade_nao_atendida > 0 ? 'atencao' : 'info'}>
                      Orçamento de <b>{brl(pedido.corte.valor_alvo)}</b>: a proposta usa{' '}
                      <b>{brl(pedido.corte.atendido)}</b>.
                      {pedido.corte.sobra_do_orcamento > 0 && (
                        <> Sobram <b>{brl(pedido.corte.sobra_do_orcamento)}</b> — a
                        necessidade real é menor que o alvo, e o sistema não completa
                        com o que não precisa.</>
                      )}
                      {pedido.corte.necessidade_nao_atendida > 0 && (
                        <> Ficam <b>{brl(pedido.corte.necessidade_nao_atendida)}</b> de
                        necessidade fora, por teto de SKU ou por limite de orçamento.</>
                      )}
                      {pedido.corte.n_limitados_por_teto > 0 && (
                        <> {pedido.corte.n_limitados_por_teto} SKU(s) foram limitados
                        pelo teto de {brl(pedido.corte.teto_por_sku_valor)}.</>
                      )}
                    </Aviso>
                  )}

                  {pedido.n_sem_ligacao > 0 && (
                    <Aviso tipo="atencao">
                      {inteiro(pedido.n_sem_ligacao)} SKU(s) somando{' '}
                      <b>{brl(pedido.valor_sem_ligacao)}</b> caem em
                      "{pedido.grupo_sem_ligacao}": existem no arquivo de estoque mas não
                      no sell-out sob o mesmo cadastro — as duas fontes trazem EANs
                      diferentes para o mesmo item físico. Eles têm velocidade (vinda do
                      próprio arquivo de estoque) mas não têm curva ABC, então{' '}
                      <b>o DDE deles precisa ser decidido a mão</b> na tabela abaixo.
                    </Aviso>
                  )}

                  <div className="mut" style={{ fontSize: 12 }}>
                    Foto de estoque de <b>{pedido.data_ref}</b>.{' '}
                    {inteiro(pedido.n_sem_giro)} SKU(s) sem venda no período ficaram fora
                    — comprar mais do que não gira é o oposto do objetivo.
                  </div>
                </div>
              </Card>

              <Card
                titulo="DDE por grupo"
                acoes={
                  pendenteGrupo ? (
                    <button className="primario" onClick={aplicarGrupos}>Recalcular</button>
                  ) : undefined
                }
              >
                <div className="pilha" style={{ gap: 8 }}>
                  <div className="mut" style={{ fontSize: 12 }}>
                    Em branco usa o DDE padrão ({ddePadrao} dias).
                  </div>
                  <table>
                    <thead>
                      <tr>
                        <th>Grupo</th>
                        <th style={{ width: 130 }}>DDE alvo</th>
                        <th className="num">SKUs</th>
                        <th className="num">Unidades</th>
                        <th className="num">Valor</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pedido.grupos.map((g) => (
                        <tr key={g.grupo}>
                          <td style={{ fontWeight: 600 }}>{g.grupo}</td>
                          <td>
                            <input
                              type="number" min={1}
                              placeholder={String(ddePadrao)}
                              value={rascunhoGrupo[g.grupo] ?? (ddeGrupo[g.grupo] ?? '')}
                              onChange={(e) =>
                                setRascunhoGrupo((r) => ({ ...r, [g.grupo]: e.target.value }))
                              }
                              onKeyDown={(e) => { if (e.key === 'Enter') aplicarGrupos() }}
                              style={{ width: 100 }}
                            />
                          </td>
                          <td className="num">{inteiro(g.skus)}</td>
                          <td className="num">{inteiro(g.unidades)}</td>
                          <td className="num" style={{ fontWeight: 600 }}>{brl(g.valor)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>

              <Card
                titulo="Proposta linha a linha"
                acoes={
                  pendenteProduto ? (
                    <button className="primario" onClick={aplicarProdutos}>Recalcular</button>
                  ) : (
                    <span className="mut" style={{ fontSize: 12 }}>
                      {isFetching ? 'recalculando...' : `${inteiro(itens.length)} linhas`}
                    </span>
                  )
                }
              >
                {itens.length === 0 ? (
                  <Vazio icone={null} titulo="Nenhum SKU precisa de reposição com estes parâmetros.">
                    Todo o estoque já cobre o DDE alvo. Aumente o DDE para ver sugestões.
                  </Vazio>
                ) : (
                  <div className="pilha" style={{ gap: 8 }}>
                    <div className="mut" style={{ fontSize: 12 }}>
                      Ajuste o DDE de qualquer linha e clique em <b>Recalcular</b>. O valor
                      da linha vence o do grupo.
                    </div>
                    <div className="rolagem">
                      <table>
                        <thead>
                          <tr>
                            <Th campo="produto" ordem={ordem} alternar={alternar}>Produto</Th>
                            <Th campo="grupo" ordem={ordem} alternar={alternar}>Grupo</Th>
                            <Th campo="classe_estoque" ordem={ordem} alternar={alternar}>Estoque</Th>
                            <Th campo="estoque_atual_un" ordem={ordem} alternar={alternar} num>Estoque</Th>
                            <Th campo="pendencia_un" ordem={ordem} alternar={alternar} num
                                titulo="Já comprado e não chegou — é descontado do pedido">
                              Pendência
                            </Th>
                            <Th campo="venda_mes" ordem={ordem} alternar={alternar} num>Venda/mês</Th>
                            <Th campo="dde_atual" ordem={ordem} alternar={alternar} num>DDE hoje</Th>
                            <th style={{ width: 100 }}>DDE alvo</th>
                            <Th campo="sugestao_un" ordem={ordem} alternar={alternar} num>Comprar</Th>
                            <Th campo="sugestao_valor" ordem={ordem} alternar={alternar} num>Valor</Th>
                          </tr>
                        </thead>
                        <tbody>
                          {itens.map((i) => (
                            <tr key={i.produto_id}>
                              <td>
                                {i.produto}
                                {i.limitado_por_teto && (
                                  <> <Tag tipo="t-hip">limitado pelo teto</Tag></>
                                )}
                              </td>
                              <td className="mut">{i.grupo}</td>
                              <td>
                                {i.classe_estoque ? (
                                  <Tag tipo={CLASSE_TAG[i.classe_estoque] ?? 't-neutro'}>
                                    {i.classe_estoque}
                                  </Tag>
                                ) : '—'}
                              </td>
                              <td className="num">{inteiro(i.estoque_atual_un)}</td>
                              <td className="num">
                                {i.pendencia_un > 0 ? inteiro(i.pendencia_un) : '—'}
                              </td>
                              <td className="num">{inteiro(i.venda_mes)}</td>
                              <td className="num">{dias(i.dde_atual)}</td>
                              <td>
                                <input
                                  type="number" min={1}
                                  placeholder={String(Math.round(i.dde_alvo))}
                                  value={rascunhoProduto[i.produto_id] ?? (ddeProduto[i.produto_id] ?? '')}
                                  onChange={(e) =>
                                    setRascunhoProduto((r) => ({ ...r, [i.produto_id]: e.target.value }))
                                  }
                                  onKeyDown={(e) => { if (e.key === 'Enter') aplicarProdutos() }}
                                  style={{ width: 76 }}
                                  title={`Vindo de: ${i.dde_origem}`}
                                />
                              </td>
                              <td className="num" style={{ fontWeight: 600 }}>{inteiro(i.sugestao_un)}</td>
                              <td className="num" style={{ fontWeight: 600 }}>{brl(i.sugestao_valor)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </Card>
            </>
          )}

          {pedido && !pedido.disponivel && (
            <Card><Vazio icone={null} titulo={pedido.motivo} /></Card>
          )}
        </div>
      )}
    </>
  )
}
