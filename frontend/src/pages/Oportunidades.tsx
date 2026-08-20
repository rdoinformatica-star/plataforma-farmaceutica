import { useQuery } from '@tanstack/react-query'
import { LineChart, Target, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { SeletorPeriodo } from '../components/dashboard/SeletorPeriodo'
import { Aviso, Card, Tag, Vazio } from '../components/ui'
import { analytics, type ItemOportunidade } from '../lib/analytics'
import { api, type Cliente } from '../lib/api'
import { brl, pct } from '../lib/format'
import { useEstado } from '../lib/estado'
import type { Periodo } from '../lib/periodo'
import { resolverPreset } from '../lib/periodo'

const TIPO_ROTULO: Record<string, string> = {
  ABC_QUEDA: 'ABC — queda', COBERTURA: 'Cobertura', MIX: 'Mix', CONCENTRACAO: 'Concentração',
}
const PRIORIDADE_TAG: Record<string, string> = { Alta: 't-erro', Média: 't-hip', Baixa: 't-neutro' }
const ALERTA_COR: Record<string, string> = {
  verde: 'var(--pos)', vermelho: 'var(--neg)', amarelo: 'var(--warn)',
  azul: 'var(--info)', roxo: '#8a5cae',
}

export function Oportunidades() {
  const { clienteAtual, setClienteAtual } = useEstado()
  const { data: clientes } = useQuery({
    queryKey: ['clientes', 'ativos'],
    queryFn: () => api.get<Cliente[]>('/clientes?ativo=true'),
  })

  if (!clienteAtual) {
    return (
      <>
        <header>
          <h1>Oportunidades</h1>
          <p className="dek">Escolha um cliente para priorizar o que atacar primeiro.</p>
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
  return <OportunidadesCliente clienteId={clienteAtual} clientes={clientes ?? []} />
}

function OportunidadesCliente({ clienteId, clientes }: { clienteId: number; clientes: Cliente[] }) {
  const { setClienteAtual } = useEstado()
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

  const [pesoPotencial, setPesoPotencial] = useState(40)
  const [pesoImpacto, setPesoImpacto] = useState(35)
  const [pesoFacilidade, setPesoFacilidade] = useState(25)
  const p = periodo
  const habilitado = !!p

  const { data: matriz, isLoading: lMatriz } = useQuery({
    queryKey: ['analytics', 'oportunidades', clienteId, p?.ini, p?.fim, pesoPotencial, pesoImpacto, pesoFacilidade],
    queryFn: () => analytics.oportunidades(clienteId, p!.ini, p!.fim, pesoPotencial, pesoImpacto, pesoFacilidade),
    enabled: habilitado,
  })
  const { data: alertas } = useQuery({
    queryKey: ['analytics', 'alertas-expandidos', clienteId, p?.ini, p?.fim],
    queryFn: () => analytics.alertasExpandidos(clienteId, p!.ini, p!.fim),
    enabled: habilitado,
  })

  if (carregandoDisp || !disp) return <Card><div className="mut">Carregando...</div></Card>

  return (
    <>
      <header>
        <div className="linha entre">
          <div>
            <h1>Oportunidades — {disp.cliente}</h1>
            <p className="dek">Junta ABC, cobertura e mix num score único — o que priorizar primeiro.</p>
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

          <Card titulo="Pesos do score" acoes={<span className="mut" style={{ fontSize: 12 }}>padrão: 40 / 35 / 25</span>}>
            <div className="linha" style={{ gap: 16, flexWrap: 'wrap' }}>
              <label style={{ width: 160, marginBottom: 0 }}>
                <span>Potencial</span>
                <input type="number" min={0} max={100} value={pesoPotencial}
                       onChange={(e) => setPesoPotencial(Number(e.target.value))} />
              </label>
              <label style={{ width: 160, marginBottom: 0 }}>
                <span>Impacto</span>
                <input type="number" min={0} max={100} value={pesoImpacto}
                       onChange={(e) => setPesoImpacto(Number(e.target.value))} />
              </label>
              <label style={{ width: 160, marginBottom: 0 }}>
                <span>Facilidade</span>
                <input type="number" min={0} max={100} value={pesoFacilidade}
                       onChange={(e) => setPesoFacilidade(Number(e.target.value))} />
              </label>
            </div>
            <div className="mut" style={{ fontSize: 11.5, marginTop: 4 }}>
              Os pesos são normalizados automaticamente — não precisam somar 100.
            </div>
          </Card>

          <Card titulo="Matriz de oportunidades">
            {lMatriz || !matriz ? (
              <div className="mut">Carregando...</div>
            ) : !matriz.disponivel ? (
              <div className="mut">{matriz.motivo}</div>
            ) : matriz.itens.length === 0 ? (
              <Vazio icone={<Target size={36} />} titulo="Nenhuma oportunidade identificada neste período." />
            ) : (
              <div className="pilha" style={{ gap: 10 }}>
                {matriz.itens.map((it: ItemOportunidade, i: number) => (
                  <div key={i} className="claim fato" style={{ margin: 0 }}>
                    <div className="linha entre">
                      <div className="linha" style={{ gap: 8 }}>
                        <Tag tipo="t-neutro">{TIPO_ROTULO[it.tipo] ?? it.tipo}</Tag>
                        <Tag tipo={PRIORIDADE_TAG[it.prioridade]}>{it.prioridade}</Tag>
                        <span className="mut" style={{ fontSize: 11 }}>{it.fonte}</span>
                      </div>
                      <span className="num" style={{ fontWeight: 700, fontSize: 15 }}>
                        {it.score.toFixed(1)}
                      </span>
                    </div>
                    <p style={{ marginTop: 8, fontWeight: 600 }}>{it.oportunidade}</p>
                    <div className="linha" style={{ gap: 16, fontSize: 12 }} >
                      <span className="mut">Potencial: <b className="num">{brl(it.potencial_estimado)}</b></span>
                      <span className="mut">Impacto: <b className="num">{pct(it.impacto_pct)}</b></span>
                      <span className="mut">Facilidade: <b className="num">{it.facilidade}</b></span>
                    </div>
                    <div className="mut" style={{ fontSize: 11.5, marginTop: 6 }}>{it.premissa}</div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card titulo="Alertas de performance">
            {alertas?.disponivel ? (
              alertas.itens.length === 0 ? (
                <Vazio icone={null} titulo="Nenhum alerta relevante neste período." />
              ) : (
                <div className="pilha" style={{ gap: 8 }}>
                  {alertas.itens.map((a, i) => (
                    <div key={i} className="linha" style={{ gap: 10, fontSize: 13 }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', flex: 'none',
                                    background: ALERTA_COR[a.tipo] ?? 'var(--muted)', marginTop: 5 }} />
                      <span>{a.texto}</span>
                    </div>
                  ))}
                </div>
              )
            ) : <div className="mut">Carregando...</div>}
          </Card>

          <Aviso tipo="info">
            Esta é a estrutura inicial da matriz de oportunidades. A priorização
            estratégica completa — descontar sobreposição entre alavancas, plano
            de ação — é de uma etapa futura.
          </Aviso>
        </div>
      )}
    </>
  )
}
