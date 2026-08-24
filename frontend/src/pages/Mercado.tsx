import { useMutation, useQuery } from '@tanstack/react-query'
import { Download, Globe, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { ComoFoiCalculado } from '../components/ComoFoiCalculado'
import { Th, useOrdenacao } from '../components/Tabela'
import { SeletorPeriodo } from '../components/dashboard/SeletorPeriodo'
import { Aviso, Card, Kpi, Tag, Vazio } from '../components/ui'
import { analytics, type Calculo } from '../lib/analytics'
import { api, type Cliente } from '../lib/api'
import { brl, inteiro, pct } from '../lib/format'
import { useEstado } from '../lib/estado'
import type { Periodo } from '../lib/periodo'
import { resolverPreset } from '../lib/periodo'

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

function pp(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)} p.p.`
}

export function Mercado() {
  const { clienteAtual, setClienteAtual } = useEstado()
  const { data: clientes } = useQuery({
    queryKey: ['clientes', 'ativos'],
    queryFn: () => api.get<Cliente[]>('/clientes?ativo=true'),
  })

  if (!clienteAtual) {
    return (
      <>
        <header>
          <h1>Mercado</h1>
          <p className="dek">Escolha um cliente para comparar a carteira dele com o mercado.</p>
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
  return <MercadoCliente clienteId={clienteAtual} clientes={clientes ?? []} />
}

function MercadoCliente({ clienteId, clientes }: { clienteId: number; clientes: Cliente[] }) {
  const { setClienteAtual } = useEstado()
  const { data: disp, isLoading: carregandoDisp } = useQuery({
    queryKey: ['analytics', 'disponibilidade', clienteId],
    queryFn: () => analytics.disponibilidade(clienteId),
  })
  const { data: perfil } = useQuery({
    queryKey: ['analytics', 'mercado-perfil', clienteId],
    queryFn: () => analytics.mercadoPerfil(clienteId),
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
  const temIqvia = perfil?.disponivel === true

  const { data: resumo } = useQuery({
    queryKey: ['analytics', 'mercado', clienteId, uf ?? ''],
    queryFn: () => analytics.mercado(clienteId, uf),
    enabled: temIqvia,
  })
  const { data: share } = useQuery({
    queryKey: ['analytics', 'mercado-share', clienteId, uf ?? ''],
    queryFn: () => analytics.mercadoShare(clienteId, uf),
    enabled: temIqvia,
  })
  const { data: shareCliente } = useQuery({
    queryKey: ['analytics', 'mercado-share-cliente', clienteId],
    queryFn: () => analytics.mercadoShareCliente(clienteId),
    enabled: temIqvia,
  })
  const { data: vs } = useQuery({
    queryKey: ['analytics', 'mercado-vs', clienteId, uf ?? ''],
    queryFn: () => analytics.mercadoVsCliente(clienteId, uf),
    enabled: temIqvia,
  })
  const { data: regional } = useQuery({
    queryKey: ['analytics', 'mercado-regional', clienteId],
    queryFn: () => analytics.mercadoRegional(clienteId),
    enabled: temIqvia,
  })
  const { data: ponte } = useQuery({
    queryKey: ['analytics', 'mercado-ponte', clienteId, periodo?.ini, periodo?.fim, uf ?? ''],
    queryFn: () => analytics.mercadoPonte(clienteId, periodo!.ini, periodo!.fim, uf),
    enabled: temIqvia && !!periodo,
  })

  const { itens: itensRegional, ordem: ordemReg, alternar: alternarReg } = useOrdenacao(
    regional?.disponivel ? regional.itens : [],
    { campo: 'mercado_valor', direcao: 'desc' },
  )
  const { itens: itensPonte, ordem: ordemPonte, alternar: alternarPonte } = useOrdenacao(
    ponte?.disponivel ? ponte.itens.slice(0, 25) : [],
  )

  const exportar = useMutation({
    mutationFn: () => analytics.mercadoXlsx(clienteId, periodo!.ini, periodo!.fim, uf),
  })

  if (carregandoDisp || !disp) return <Card><div className="mut">Carregando...</div></Card>

  const ufs = regional?.disponivel ? regional.itens.map((i) => i.uf) : []

  return (
    <>
      <header>
        <div className="linha entre">
          <div>
            <h1>Mercado — {disp.cliente}</h1>
            <p className="dek">Tamanho, crescimento e participação da indústria (IQVIA).</p>
          </div>
          <div className="linha" style={{ gap: 10, alignItems: 'flex-end' }}>
            <button disabled={exportar.isPending || !temIqvia || !periodo} onClick={() => exportar.mutate()}>
              <Download size={14} />
              {exportar.isPending ? 'Gerando...' : 'Exportar Excel'}
            </button>
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
        </div>
        {exportar.isError && (
          <Aviso tipo="atencao">{(exportar.error as Error).message}</Aviso>
        )}
      </header>

      {perfil && !perfil.disponivel ? (
        <Card>
          <Vazio
            icone={<Globe size={36} />}
            titulo="Nenhuma base de mercado (IQVIA) importada."
            acao={<Link to="/importar" className="btn primario">Importar mercado</Link>}
          >
            {perfil.motivo}
          </Vazio>
        </Card>
      ) : (
        <div className="pilha">
          <Aviso tipo="atencao">
            <b>O que esta base mede.</b> A IQVIA identifica <b>laboratório</b> (a
            indústria), nunca o distribuidor. Por isso o share mostrado aqui é da{' '}
            <b>VITAMEDIC no varejo</b> — não é a fatia de {disp.cliente}. Os dois lados
            também medem elos diferentes: a IQVIA é a venda do PDV ao consumidor; o
            sell-out do cliente é a venda do distribuidor ao PDV.
          </Aviso>

          {perfil?.disponivel && (
            <Card titulo="Perfil da fonte" acoes={comoCalculado('Como a fonte foi lida', perfil.calculo)}>
              <div className="kpis">
                <Kpi rotulo="Linhas" valor={inteiro(perfil.linhas)} />
                <Kpi rotulo="Período de referência" valor={String(perfil.periodo_ref)} />
                <Kpi
                  rotulo="Janela comparada"
                  valor={`${perfil.janela_ytd.ini}–${perfil.janela_ytd.fim}`}
                  sub={`contra ${perfil.janela_ytd.ini_ant}–${perfil.janela_ytd.fim_ant}`}
                />
                <Kpi rotulo="Mercados" valor={inteiro(perfil.dimensoes.mercados)} />
                <Kpi rotulo="Moléculas" valor={inteiro(perfil.dimensoes.moleculas)} />
                <Kpi rotulo="UFs" valor={inteiro(perfil.dimensoes.ufs)} />
              </div>
              <div className="linha" style={{ gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                <Tag tipo="t-neutro">{perfil.eh_foto_unica ? 'foto única (sem série mensal)' : 'série disponível'}</Tag>
                <Tag tipo="t-erro">não identifica distribuidor</Tag>
                <Tag tipo={perfil.tem_ligacao_com_dim_product ? 't-ok' : 't-hip'}>
                  {perfil.tem_ligacao_com_dim_product ? 'ligado ao cadastro' : 'sem chave com o cadastro'}
                </Tag>
              </div>
            </Card>
          )}

          <div className="linha" style={{ gap: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <label style={{ width: 180, marginBottom: 0 }}>
              <span>UF</span>
              <select value={uf ?? ''} onChange={(e) => setUf(e.target.value || undefined)}>
                <option value="">Brasil (nacional)</option>
                {ufs.map((u) => (
                  <option key={u} value={u}>{u}</option>
                ))}
              </select>
            </label>
          </div>

          {resumo?.disponivel && share?.disponivel && (
            <div className="kpis">
              <Kpi rotulo="Mercado (valor, YTD)" valor={brl(resumo.valor_ytd)} />
              <Kpi
                rotulo="Crescimento do mercado"
                valor={resumo.cresc_valor_pct === null ? '—' : pct(resumo.cresc_valor_pct)}
                sub="em valor, YTD vs ano anterior"
              />
              <Kpi rotulo="Mercado (unidades, YTD)" valor={inteiro(resumo.unidades_ytd)} />
              <Kpi
                rotulo="Share da indústria"
                valor={pct(share.share_pct)}
                sub={`${pp(share.delta_share_pp)} vs ano anterior`}
              />
            </div>
          )}

          {shareCliente && (
            <Card titulo="Share do cliente no mercado">
              <Aviso tipo="erro">{shareCliente.motivo}</Aviso>
            </Card>
          )}

          <Card
            titulo="Crescimento do cliente vs mercado"
            acoes={vs?.disponivel ? comoCalculado('Como a comparação foi feita', vs.calculo) : undefined}
          >
            {vs?.disponivel ? (
              <div className="pilha" style={{ gap: 10 }}>
                <table>
                  <thead>
                    <tr>
                      <th>Base</th>
                      <th className="num">Cliente</th>
                      <th className="num">Mercado</th>
                      <th className="num">Diferença</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td style={{ fontWeight: 600 }}>Valor</td>
                      <td className="num">
                        {vs.cliente.cresc_valor_pct === null ? '—' : pct(vs.cliente.cresc_valor_pct)}
                      </td>
                      <td className="num">
                        {vs.mercado.cresc_valor_pct === null ? '—' : pct(vs.mercado.cresc_valor_pct)}
                      </td>
                      <td className="num" style={{ fontWeight: 700 }}>{pp(vs.diferenca_valor_pp)}</td>
                    </tr>
                    <tr>
                      <td style={{ fontWeight: 600 }}>Unidades</td>
                      <td className="num">
                        {vs.cliente.cresc_unidades_pct === null ? '—' : pct(vs.cliente.cresc_unidades_pct)}
                      </td>
                      <td className="num">
                        {vs.mercado.cresc_unidades_pct === null ? '—' : pct(vs.mercado.cresc_unidades_pct)}
                      </td>
                      <td className="num" style={{ fontWeight: 700 }}>{pp(vs.diferenca_unidades_pp)}</td>
                    </tr>
                  </tbody>
                </table>

                {vs.leitura_valor && (
                  <div className="claim fato" style={{ margin: 0 }}>
                    <div className="linha" style={{ gap: 8 }}>
                      <Tag tipo="t-neutro">FATO</Tag>
                      <span style={{ fontWeight: 600 }}>Em valor</span>
                    </div>
                    <p style={{ marginTop: 6 }}>{vs.leitura_valor}</p>
                  </div>
                )}
                {vs.leitura_unidades && (
                  <div className="claim fato" style={{ margin: 0 }}>
                    <div className="linha" style={{ gap: 8 }}>
                      <Tag tipo="t-neutro">FATO</Tag>
                      <span style={{ fontWeight: 600 }}>Em unidades</span>
                    </div>
                    <p style={{ marginTop: 6 }}>{vs.leitura_unidades}</p>
                  </div>
                )}

                <Aviso tipo="info">
                  Janela imposta pela fonte de mercado ({vs.janela.ini}–{vs.janela.fim} contra{' '}
                  {vs.janela.ini_ant}–{vs.janela.fim_ant}); o cliente foi medido na mesma
                  janela, não no período selecionado. A comparação é de <b>ritmo de
                  crescimento</b>, não de tamanho — os valores absolutos não são somáveis
                  entre si.
                </Aviso>
              </div>
            ) : (
              <div className="mut">{vs?.motivo ?? 'Carregando...'}</div>
            )}
          </Card>

          <Card
            titulo="Mercado por UF"
            acoes={regional?.disponivel ? comoCalculado('Como o regional foi calculado', regional.calculo) : undefined}
          >
            {regional?.disponivel ? (
              <div className="rolagem">
                <table>
                  <thead>
                    <tr>
                      <Th campo="uf" ordem={ordemReg} alternar={alternarReg}>UF</Th>
                      <Th campo="mercado_valor" ordem={ordemReg} alternar={alternarReg} num>Mercado (R$)</Th>
                      <Th campo="mercado_un" ordem={ordemReg} alternar={alternarReg} num>Mercado (un)</Th>
                      <Th campo="vitamedic_un" ordem={ordemReg} alternar={alternarReg} num>Indústria (un)</Th>
                      <Th campo="share_pct" ordem={ordemReg} alternar={alternarReg} num>Share</Th>
                      <Th campo="delta_share_pp" ordem={ordemReg} alternar={alternarReg} num>Δ share</Th>
                      <Th campo="cresc_mercado_pct" ordem={ordemReg} alternar={alternarReg} num>Cresc. mercado</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {itensRegional.map((i) => (
                      <tr key={i.uf}>
                        <td style={{ fontWeight: 600 }}>{i.uf}</td>
                        <td className="num">{brl(i.mercado_valor)}</td>
                        <td className="num">{inteiro(i.mercado_un)}</td>
                        <td className="num">{inteiro(i.vitamedic_un)}</td>
                        <td className="num">{pct(i.share_pct)}</td>
                        <td className="num">{pp(i.delta_share_pp)}</td>
                        <td className="num">
                          {i.cresc_mercado_pct === null ? '—' : pct(i.cresc_mercado_pct)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="mut">{regional?.motivo ?? 'Carregando...'}</div>
            )}
          </Card>

          <Card
            titulo="Produtos do cliente × mercado"
            acoes={ponte?.disponivel ? comoCalculado('Como a ponte foi construída', ponte.calculo) : undefined}
          >
            {ponte?.disponivel ? (
              <div className="pilha" style={{ gap: 10 }}>
                <div className="kpis">
                  <Kpi rotulo="SKUs ligados" valor={inteiro(ponte.n_ligados)} />
                  <Kpi rotulo="Sem correspondência" valor={inteiro(ponte.n_sem_correspondencia)} />
                  <Kpi
                    rotulo="Cobertura da ponte"
                    valor={ponte.cobertura_da_ponte_pct === null ? '—' : pct(ponte.cobertura_da_ponte_pct)}
                    sub="do faturamento do cliente"
                  />
                </div>

                <Aviso tipo="atencao">
                  A ponte é <b>parcial</b>: a base não traz chave entre as duas fontes e os
                  nomes divergem. O nível <b>molécula</b> compara o produto com o mercado da
                  molécula inteira (outras dosagens e embalagens juntas) — serve de contexto
                  competitivo, não de share do SKU.
                </Aviso>

                <div className="rolagem">
                  <table>
                    <thead>
                      <tr>
                        <Th campo="produto" ordem={ordemPonte} alternar={alternarPonte}>Produto</Th>
                        <Th campo="nivel_ligacao" ordem={ordemPonte} alternar={alternarPonte}>Ligação</Th>
                        <Th campo="referencia_mercado" ordem={ordemPonte} alternar={alternarPonte}>Referência no mercado</Th>
                        <Th campo="faturamento_cliente" ordem={ordemPonte} alternar={alternarPonte} num>Faturamento</Th>
                        <Th campo="share_industria_pct" ordem={ordemPonte} alternar={alternarPonte} num>Share da indústria</Th>
                        <Th campo="delta_share_pp" ordem={ordemPonte} alternar={alternarPonte} num>Δ share</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {itensPonte.map((i) => (
                        <tr key={i.produto_id}>
                          <td>{i.produto}</td>
                          <td>
                            <Tag tipo={i.nivel_ligacao === 'apresentacao' ? 't-ok' : 't-hip'}>
                              {i.nivel_ligacao === 'apresentacao' ? 'SKU exato' : 'molécula'}
                            </Tag>
                          </td>
                          <td className="mut">{i.referencia_mercado}</td>
                          <td className="num">{brl(i.faturamento_cliente)}</td>
                          <td className="num">{pct(i.share_industria_pct)}</td>
                          <td className="num">{pp(i.delta_share_pp)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {ponte.sem_correspondencia.length > 0 && (
                  <details>
                    <summary className="mut" style={{ cursor: 'pointer', fontSize: 13 }}>
                      {ponte.n_sem_correspondencia} produto(s) sem correspondência no mercado
                    </summary>
                    <table style={{ marginTop: 8 }}>
                      <tbody>
                        {ponte.sem_correspondencia.slice(0, 15).map((s) => (
                          <tr key={s.produto_id}>
                            <td>{s.produto}</td>
                            <td className="num">{brl(s.faturamento)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </details>
                )}
              </div>
            ) : (
              <div className="mut">{ponte?.motivo ?? 'Carregando...'}</div>
            )}
          </Card>

          {disponivel && (
            <SeletorPeriodo disponivel={disponivel} valor={periodo ?? disponivel} aoMudar={setPeriodo} />
          )}
        </div>
      )}
    </>
  )
}
