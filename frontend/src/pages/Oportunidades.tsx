import { useQuery } from '@tanstack/react-query'
import { LineChart, Target, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { useOrdenacao } from '../components/Tabela'
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

  const { itens: itensMatriz, ordem: ordemMatriz, alternar: alternarMatriz } = useOrdenacao(
    matriz?.disponivel ? matriz.itens : [],
    { campo: 'score', direcao: 'desc' },
  )

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

          <Card titulo="O que significa cada número">
            <div className="grade c3">
              <div>
                <div className="rot">Potencial</div>
                <p style={{ marginTop: 4, fontSize: 13 }}>
                  Valor em <b>R$</b> que a oportunidade representa. Numa queda de produto
                  A, é o quanto o faturamento caiu; numa cobertura baixa, é o ganho
                  estimado de vender para mais PDVs no ritmo médio atual; numa
                  concentração alta, é uma fatia de referência (5%) do faturamento do
                  período.
                </p>
              </div>
              <div>
                <div className="rot">Impacto</div>
                <p style={{ marginTop: 4, fontSize: 13 }}>
                  <b>%</b> que aquele produto ou PDV já representa no faturamento total do
                  cliente no período. Um impacto alto significa que a oportunidade está
                  numa parte grande da carteira — mexer nela move o resultado como um
                  todo, não é um detalhe.
                </p>
              </div>
              <div>
                <div className="rot">Facilidade</div>
                <p style={{ marginTop: 4, fontSize: 13 }}>
                  Nota fixa por <b>tipo</b> de oportunidade (não calculada por produto):
                  cobertura 70, mix 55, queda de ABC 35, concentração 30. Reflete o quão
                  direto costuma ser agir sobre aquele tipo de ação — vender mais numa
                  praça já testada é mais simples do que reverter uma queda cuja causa
                  não está nos dados.
                </p>
              </div>
            </div>
            <div className="mut" style={{ fontSize: 12, marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
              <b>Como priorizar:</b> o score junta os três — comece pelas de{' '}
              <Tag tipo="t-erro">Alta</Tag> prioridade e maior score. Dentro da mesma
              prioridade, olhe o <b>potencial em R$</b> se o objetivo é receita, ou a{' '}
              <b>facilidade</b> se você quer um resultado rápido para testar antes de ir
              atrás das mais difíceis. Os pesos acima mudam quanto cada critério pesa no
              score — suba "Facilidade" se quer priorizar o que é mais rápido de
              executar, suba "Potencial" se quer priorizar o maior R$ possível.
            </div>
          </Card>

          <Card
            titulo="Matriz de oportunidades"
            acoes={
              matriz?.disponivel && matriz.itens.length > 0 ? (
                <label style={{ marginBottom: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span className="mut" style={{ fontSize: 12 }}>Ordenar por</span>
                  <select
                    value={ordemMatriz?.campo ?? 'score'}
                    onChange={(e) =>
                      alternarMatriz(
                        e.target.value as keyof ItemOportunidade & string,
                        e.target.value === 'oportunidade' || e.target.value === 'tipo' ? 'texto' : 'numero',
                      )
                    }
                    style={{ width: 160 }}
                  >
                    <option value="score">Score</option>
                    <option value="potencial_estimado">Potencial</option>
                    <option value="impacto_pct">Impacto</option>
                    <option value="facilidade">Facilidade</option>
                    <option value="oportunidade">Oportunidade (A–Z)</option>
                  </select>
                </label>
              ) : undefined
            }
          >
            {lMatriz || !matriz ? (
              <div className="mut">Carregando...</div>
            ) : !matriz.disponivel ? (
              <div className="mut">{matriz.motivo}</div>
            ) : matriz.itens.length === 0 ? (
              <Vazio icone={<Target size={36} />} titulo="Nenhuma oportunidade identificada neste período." />
            ) : (
              <div className="pilha" style={{ gap: 10 }}>
                {itensMatriz.map((it: ItemOportunidade, i: number) => (
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
