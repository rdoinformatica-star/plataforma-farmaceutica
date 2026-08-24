import { useMutation, useQuery } from '@tanstack/react-query'
import { Download, LineChart, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { ComoFoiCalculado } from '../components/ComoFoiCalculado'
import { Th, useOrdenacao } from '../components/Tabela'
import { SeletorPeriodo } from '../components/dashboard/SeletorPeriodo'
import { Aviso, Card, Kpi, Tag, Vazio } from '../components/ui'
import { analytics } from '../lib/analytics'
import { api, type Cliente } from '../lib/api'
import { brl, inteiro, pct } from '../lib/format'
import { useEstado } from '../lib/estado'
import type { Periodo } from '../lib/periodo'
import { resolverPreset } from '../lib/periodo'

const QUADRANTE_INFO: Record<string, { tag: string; rotulo: string; leitura: string }> = {
  PRIORITARIO: {
    tag: 't-erro',
    rotulo: 'Prioritário',
    leitura: 'Fatura acima da mediana com cobertura abaixo dela: vende bem onde está, mas está em poucos PDVs.',
  },
  CONSOLIDADO: {
    tag: 't-fato',
    rotulo: 'Consolidado',
    leitura: 'Fatura acima da mediana e já cobre acima dela: o produto está distribuído e performando.',
  },
  INVESTIGAR_PRODUTIVIDADE: {
    tag: 't-hip',
    rotulo: 'Investigar produtividade',
    leitura: 'Cobertura acima da mediana mas faturamento abaixo: está em muitos PDVs e rende pouco em cada um.',
  },
  BAIXA_PRIORIDADE: {
    tag: 't-neutro',
    rotulo: 'Baixa prioridade',
    leitura: 'Faturamento e cobertura abaixo da mediana: pouco alcance e pouco retorno no período.',
  },
}
const ORDEM_QUADRANTES = [
  'PRIORITARIO',
  'CONSOLIDADO',
  'INVESTIGAR_PRODUTIVIDADE',
  'BAIXA_PRIORIDADE',
] as const
const INCREMENTOS = [5, 10, 15, 20]

export function Cobertura() {
  const { clienteAtual, setClienteAtual } = useEstado()
  const { data: clientes } = useQuery({
    queryKey: ['clientes', 'ativos'],
    queryFn: () => api.get<Cliente[]>('/clientes?ativo=true'),
  })

  if (!clienteAtual) {
    return (
      <>
        <header>
          <h1>Cobertura comercial</h1>
          <p className="dek">Escolha um cliente para ver quanto da carteira cada produto alcança.</p>
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
  return <CoberturaCliente clienteId={clienteAtual} clientes={clientes ?? []} />
}

function CoberturaCliente({ clienteId, clientes }: { clienteId: number; clientes: Cliente[] }) {
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

  const [incrementoPp, setIncrementoPp] = useState(10)
  const [quadrante, setQuadrante] = useState<string | null>(null)
  const p = periodo
  const habilitado = !!p

  const { data: cobertura } = useQuery({
    queryKey: ['analytics', 'cobertura', clienteId, p?.ini, p?.fim],
    queryFn: () => analytics.cobertura(clienteId, p!.ini, p!.fim, undefined, 200),
    enabled: habilitado,
  })
  const { data: matriz } = useQuery({
    queryKey: ['analytics', 'cobertura-matriz', clienteId, p?.ini, p?.fim],
    queryFn: () => analytics.coberturaMatriz(clienteId, p!.ini, p!.fim),
    enabled: habilitado,
  })
  const { data: potencial } = useQuery({
    queryKey: ['analytics', 'cobertura-potencial', clienteId, p?.ini, p?.fim, incrementoPp],
    queryFn: () => analytics.coberturaPotencial(clienteId, p!.ini, p!.fim, incrementoPp),
    enabled: habilitado,
  })

  const doQuadrante =
    matriz?.disponivel && quadrante
      ? matriz.itens.filter((i) => i.quadrante === quadrante)
      : []
  const { itens: itensQuadrante, ordem: ordemQ, alternar: alternarQ } =
    useOrdenacao(doQuadrante, { campo: 'faturamento_atual', direcao: 'desc' })
  const { itens: itensPotencial, ordem: ordemP, alternar: alternarP } =
    useOrdenacao(potencial?.disponivel ? potencial.itens : [])
  const { itens: itensCobertura, ordem: ordemC, alternar: alternarC } =
    useOrdenacao(cobertura?.disponivel ? cobertura.itens.slice(0, 100) : [])

  const exportar = useMutation({
    mutationFn: () => analytics.coberturaXlsx(clienteId, p!.ini, p!.fim, incrementoPp),
  })

  if (carregandoDisp || !disp) return <Card><div className="mut">Carregando...</div></Card>

  return (
    <>
      <header>
        <div className="linha entre">
          <div>
            <h1>Cobertura — {disp.cliente}</h1>
            <p className="dek">PDVs compradores de cada produto / PDVs da carteira do cliente.</p>
          </div>
          <div className="linha" style={{ gap: 10, alignItems: 'flex-end' }}>
            <button disabled={exportar.isPending || !habilitado} onClick={() => exportar.mutate()}>
              <Download size={14} />
              {exportar.isPending ? 'Gerando...' : 'Exportar Excel'}
            </button>
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

          {cobertura?.disponivel && (
            <Card>
              <div className="kpis">
                <Kpi rotulo="PDVs da base" valor={inteiro(cobertura.pdvs_base)}
                     sub="compraram qualquer produto do cliente" />
                <Kpi rotulo="Produtos analisados" valor={inteiro(cobertura.total)} />
              </div>
            </Card>
          )}

          {matriz?.disponivel && (
            <Card titulo="Matriz cobertura × faturamento" acoes={
              <ComoFoiCalculado calculo={{
                titulo: 'Como a matriz foi calculada', formula: matriz.calculo.formula,
                valores: [
                  { rotulo: 'Mediana de faturamento', valor: brl(matriz.mediana_faturamento) },
                  { rotulo: 'Mediana de cobertura', valor: pct(matriz.mediana_cobertura_pct) },
                ],
                premissas: matriz.calculo.premissas,
              }} />
            }>
              <div className="grade c2">
                {ORDEM_QUADRANTES.map((chave) => {
                  const info = QUADRANTE_INFO[chave]
                  const n = matriz.resumo[chave] ?? 0
                  const ativo = quadrante === chave
                  return (
                    <button
                      key={chave}
                      onClick={() => setQuadrante(ativo ? null : chave)}
                      className={`quadrante${ativo ? ' ativo' : ''}`}
                      disabled={n === 0}
                    >
                      <span className="linha entre">
                        <Tag tipo={info.tag}>{info.rotulo}</Tag>
                        <span className="num" style={{ fontWeight: 600 }}>{n} produtos</span>
                      </span>
                      <span className="mut" style={{ fontSize: 12, display: 'block', marginTop: 6 }}>
                        {info.leitura}
                      </span>
                      {n > 0 && (
                        <span className="mut" style={{ fontSize: 11.5, display: 'block', marginTop: 6 }}>
                          {ativo ? '▾ mostrando os produtos abaixo' : '▸ clique para ver quais são'}
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>

              {quadrante && (
                <div style={{ marginTop: 14 }}>
                  <div className="linha entre" style={{ marginBottom: 8 }}>
                    <b style={{ fontSize: 13 }}>
                      Produtos em “{QUADRANTE_INFO[quadrante].rotulo}” ({doQuadrante.length})
                    </b>
                    <button onClick={() => setQuadrante(null)}>Fechar</button>
                  </div>
                  <div className="rolagem">
                    <table>
                      <thead>
                        <tr>
                          <Th campo="produto" ordem={ordemQ} alternar={alternarQ}>Produto</Th>
                          <Th campo="faturamento_atual" ordem={ordemQ} alternar={alternarQ} num>Faturamento</Th>
                          <Th campo="pdvs_compradores" ordem={ordemQ} alternar={alternarQ} num>PDVs</Th>
                          <Th campo="cobertura_pct" ordem={ordemQ} alternar={alternarQ} num>Cobertura</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {itensQuadrante.map((it) => (
                          <tr key={it.produto_id}>
                            <td>{it.produto}</td>
                            <td className="num">{brl(it.faturamento_atual)}</td>
                            <td className="num">{inteiro(it.pdvs_compradores)}</td>
                            <td className="num">{pct(it.cobertura_pct)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="mut" style={{ fontSize: 11.5, marginTop: 8 }}>
                    Corte pela mediana do recorte atual: faturamento {brl(matriz.mediana_faturamento)} ·
                    cobertura {pct(matriz.mediana_cobertura_pct)}. Mudar período ou UF move o corte —
                    o quadrante é relativo aos produtos deste recorte, não uma classificação absoluta.
                  </div>
                </div>
              )}
            </Card>
          )}

          <Card titulo="Simulador de potencial de cobertura" acoes={
            <div className="linha" style={{ gap: 6 }}>
              {INCREMENTOS.map((n) => (
                <button key={n} className={incrementoPp === n ? 'primario' : ''} onClick={() => setIncrementoPp(n)}>
                  +{n}pp
                </button>
              ))}
            </div>
          }>
            {potencial?.disponivel ? (
              <div className="pilha">
                <Aviso tipo="info">
                  <b>POTENCIAL ESTIMADO — não é venda garantida.</b> {potencial.calculo.premissas?.[0]}
                </Aviso>
                <div className="kpis">
                  <Kpi rotulo={`+${incrementoPp}pp de cobertura`} valor={`${inteiro(potencial.pdvs_incremento)} PDVs`} />
                  <Kpi rotulo="Potencial no período" valor={brl(potencial.potencial_estimado_total)} />
                  <Kpi rotulo="Potencial anualizado" valor={brl(potencial.potencial_estimado_anual)} />
                </div>
                <div className="rolagem">
                  <table>
                    <thead>
                      <tr>
                        <Th campo="produto" ordem={ordemP} alternar={alternarP}>Produto</Th>
                        <Th campo="cobertura_pct" ordem={ordemP} alternar={alternarP} num>Cobertura</Th>
                        <Th campo="rs_por_pdv" ordem={ordemP} alternar={alternarP} num>R$/PDV</Th>
                        <Th campo="potencial_estimado" ordem={ordemP} alternar={alternarP} num>Potencial</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {itensPotencial.map((it) => (
                        <tr key={it.produto_id}>
                          <td>{it.produto}</td>
                          <td className="num">{pct(it.cobertura_pct)}</td>
                          <td className="num">{brl(it.rs_por_pdv)}</td>
                          <td className="num pos">{brl(it.potencial_estimado)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {potencial.sem_dado_suficiente.length > 0 && (
                  <Aviso tipo="atencao">
                    {potencial.sem_dado_suficiente.length} produto(s) com poucos PDVs compradores
                    ficaram de fora da conta (R$/PDV pouco confiável com amostra pequena):{' '}
                    {potencial.sem_dado_suficiente.map((s) => s.produto).join(', ')}.
                  </Aviso>
                )}
              </div>
            ) : (
              <div className="mut">{potencial && !potencial.disponivel ? potencial.motivo : 'Carregando...'}</div>
            )}
          </Card>

          <Card titulo="Cobertura por produto">
            {!cobertura?.disponivel ? (
              <div className="mut">{cobertura ? cobertura.motivo : 'Carregando...'}</div>
            ) : (
              <div className="rolagem">
                <table>
                  <thead>
                    <tr>
                      <Th campo="produto" ordem={ordemC} alternar={alternarC}>Produto</Th>
                      <Th campo="faturamento_atual" ordem={ordemC} alternar={alternarC} num>Faturamento</Th>
                      <Th campo="pdvs_compradores" ordem={ordemC} alternar={alternarC} num>PDVs compradores</Th>
                      <Th campo="cobertura_pct" ordem={ordemC} alternar={alternarC} num>Cobertura</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {itensCobertura.map((it) => (
                      <tr key={it.produto_id}>
                        <td>{it.produto}</td>
                        <td className="num">{brl(it.faturamento_atual)}</td>
                        <td className="num">{inteiro(it.pdvs_compradores)}</td>
                        <td className="num">{pct(it.cobertura_pct)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}
    </>
  )
}
