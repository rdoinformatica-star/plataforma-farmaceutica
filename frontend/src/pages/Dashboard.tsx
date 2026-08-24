import { useMutation, useQuery } from '@tanstack/react-query'
import { Download, LineChart, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { AnalisePDV } from '../components/dashboard/AnalisePDV'
import { AnaliseUF } from '../components/dashboard/AnaliseUF'
import { Alertas } from '../components/dashboard/Alertas'
import { Concentracao } from '../components/dashboard/Concentracao'
import { EvolucaoMensal } from '../components/dashboard/EvolucaoMensal'
import { RankingProdutos } from '../components/dashboard/RankingProdutos'
import { ResumoExecutivo } from '../components/dashboard/ResumoExecutivo'
import { SeletorPeriodo } from '../components/dashboard/SeletorPeriodo'
import { VariacaoProdutos } from '../components/dashboard/VariacaoProdutos'
import { Aviso, Card, Vazio } from '../components/ui'
import { analytics } from '../lib/analytics'
import { api, type Cliente } from '../lib/api'
import { faixaPeriodo } from '../lib/format'
import { useEstado } from '../lib/estado'
import type { Periodo } from '../lib/periodo'
import { resolverPreset } from '../lib/periodo'

export function Dashboard() {
  const { clienteAtual, setClienteAtual } = useEstado()
  const { data: clientes } = useQuery({
    queryKey: ['clientes', 'ativos'],
    queryFn: () => api.get<Cliente[]>('/clientes?ativo=true'),
  })

  if (!clienteAtual) {
    return (
      <>
        <header>
          <h1>Desempenho</h1>
          <p className="dek">Escolha um cliente para ver o desempenho comercial.</p>
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

  return <DashboardCliente clienteId={clienteAtual} clientes={clientes ?? []} />
}

function DashboardCliente({ clienteId, clientes }: { clienteId: number; clientes: Cliente[] }) {
  const { setClienteAtual } = useEstado()
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

  const [metrica, setMetrica] = useState('faturamento')
  const [ordenar, setOrdenar] = useState('faturamento')
  const [limiteProdutos, setLimiteProdutos] = useState(10)
  const [visaoPdv, setVisaoPdv] = useState('ranking')
  const [contextoConcentracao, setContextoConcentracao] = useState<'produtos' | 'pdvs'>('produtos')
  // UF por ranking: o usuario pode querer olhar produtos do RJ e PDVs do ES
  // ao mesmo tempo. Um estado so forcaria os dois juntos.
  const [ufProdutos, setUfProdutos] = useState<string | undefined>(undefined)
  const [ufPdvs, setUfPdvs] = useState<string | undefined>(undefined)

  const p = periodo
  const habilitado = !!p

  const { data: resumo, isLoading: lResumo } = useQuery({
    queryKey: ['analytics', 'resumo', clienteId, p?.ini, p?.fim],
    queryFn: () => analytics.resumo(clienteId, p!.ini, p!.fim),
    enabled: habilitado,
  })
  const { data: evolucao, isLoading: lEvolucao } = useQuery({
    queryKey: ['analytics', 'evolucao', clienteId, disponivel?.ini, disponivel?.fim, metrica],
    queryFn: () => analytics.evolucaoMensal(clienteId, disponivel!.ini, disponivel!.fim, metrica),
    enabled: !!disponivel,
  })
  const { data: ranking, isLoading: lRanking } = useQuery({
    queryKey: ['analytics', 'produtos', clienteId, p?.ini, p?.fim, ordenar, limiteProdutos, ufProdutos ?? ''],
    queryFn: () => analytics.produtos(clienteId, p!.ini, p!.fim, ordenar, limiteProdutos, 0, ufProdutos),
    enabled: habilitado,
  })
  const { data: potProdutos } = useQuery({
    queryKey: ['analytics', 'potencial-produtos', clienteId, p?.ini, p?.fim, ufProdutos ?? ''],
    queryFn: () => analytics.potencialProdutos(clienteId, p!.ini, p!.fim, ufProdutos),
    enabled: habilitado,
  })
  const { data: potPdvs } = useQuery({
    queryKey: ['analytics', 'potencial-pdvs', clienteId, p?.ini, p?.fim, ufPdvs ?? ''],
    queryFn: () => analytics.potencialPdvs(clienteId, p!.ini, p!.fim, ufPdvs),
    enabled: habilitado,
  })
  const { data: crescimento, isLoading: lCrescimento } = useQuery({
    queryKey: ['analytics', 'variacao', 'crescimento', clienteId, p?.ini, p?.fim],
    queryFn: () => analytics.produtosVariacao(clienteId, p!.ini, p!.fim, 'crescimento'),
    enabled: habilitado,
  })
  const { data: queda, isLoading: lQueda } = useQuery({
    queryKey: ['analytics', 'variacao', 'queda', clienteId, p?.ini, p?.fim],
    queryFn: () => analytics.produtosVariacao(clienteId, p!.ini, p!.fim, 'queda'),
    enabled: habilitado,
  })
  const { data: uf, isLoading: lUf } = useQuery({
    queryKey: ['analytics', 'uf', clienteId, p?.ini, p?.fim],
    queryFn: () => analytics.uf(clienteId, p!.ini, p!.fim),
    enabled: habilitado,
  })
  const { data: pdvs, isLoading: lPdvs } = useQuery({
    queryKey: ['analytics', 'pdvs', clienteId, p?.ini, p?.fim, visaoPdv, ufPdvs ?? ''],
    queryFn: () => analytics.pdvs(
      clienteId, p!.ini, p!.fim, visaoPdv as 'ranking' | 'novos' | 'sumidos', 20, ufPdvs),
    enabled: habilitado,
  })
  const { data: concentracao, isLoading: lConcentracao } = useQuery({
    queryKey: ['analytics', 'concentracao', clienteId, p?.ini, p?.fim, contextoConcentracao],
    queryFn: () => analytics.concentracao(clienteId, p!.ini, p!.fim, contextoConcentracao),
    enabled: habilitado,
  })
  const { data: alertas, isLoading: lAlertas } = useQuery({
    queryKey: ['analytics', 'alertas', clienteId, p?.ini, p?.fim],
    queryFn: () => analytics.alertas(clienteId, p!.ini, p!.fim),
    enabled: habilitado,
  })

  const exportar = useMutation({
    mutationFn: () => analytics.dashboardXlsx(clienteId, p!.ini, p!.fim, ordenar, ufProdutos, ufPdvs),
  })

  if (carregandoDisp || !disp) {
    return (
      <>
        <header><h1>Desempenho</h1></header>
        <Card><Vazio icone={<LineChart size={36} />} titulo="Carregando..." /></Card>
      </>
    )
  }

  return (
    <>
      <header>
        <div className="linha entre">
          <div>
            <h1>{disp.cliente}</h1>
            <p className="dek">Desempenho comercial — sell-out</p>
          </div>
          <div className="linha" style={{ gap: 10, alignItems: 'flex-end' }}>
            <button disabled={exportar.isPending || !habilitado} onClick={() => exportar.mutate()}>
              <Download size={14} />
              {exportar.isPending ? 'Gerando...' : 'Exportar Excel'}
            </button>
            <select value={clienteId} onChange={(e) => setClienteAtual(Number(e.target.value))} style={{ width: 200 }}>
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

      {!disp.tem_sellout ? (
        <Card>
          <Vazio
            icone={<LineChart size={36} />}
            titulo="Este cliente ainda não possui dados suficientes para esta análise."
            acao={<Link to="/importar" className="btn primario">Importar um relatório</Link>}
          >
            {disp.motivo_indisponivel}
          </Vazio>
        </Card>
      ) : (
        <div className="pilha">
          {disponivel && (
            <SeletorPeriodo
              disponivel={disponivel}
              valor={periodo ?? disponivel}
              aoMudar={setPeriodo}
            />
          )}
          <div className="mut" style={{ fontSize: 12 }}>
            Dados disponíveis: {faixaPeriodo(disp.periodo_min, disp.periodo_max)}
          </div>

          {resumo ? (
            <ResumoExecutivo resumo={resumo} />
          ) : lResumo ? (
            <Card><div className="mut">Carregando resumo...</div></Card>
          ) : null}

          <EvolucaoMensal dados={evolucao} metrica={metrica} setMetrica={setMetrica} carregando={lEvolucao} />

          <div className="grade c2">
            <VariacaoProdutos titulo="Produtos em crescimento" dados={crescimento} carregando={lCrescimento} />
            <VariacaoProdutos titulo="Produtos em queda" dados={queda} carregando={lQueda} />
          </div>

          <RankingProdutos
            dados={ranking} ordenar={ordenar} setOrdenar={setOrdenar}
            limite={limiteProdutos} setLimite={setLimiteProdutos} carregando={lRanking}
            ufs={uf} uf={ufProdutos} setUf={setUfProdutos} potencial={potProdutos}
          />

          <div className="grade c2">
            <AnaliseUF dados={uf} carregando={lUf} />
            <Concentracao
              dados={concentracao} contexto={contextoConcentracao}
              setContexto={(c) => setContextoConcentracao(c as 'produtos' | 'pdvs')}
              carregando={lConcentracao}
            />
          </div>

          <AnalisePDV
            dados={pdvs} visao={visaoPdv} setVisao={setVisaoPdv} carregando={lPdvs}
            ufs={uf} uf={ufPdvs} setUf={setUfPdvs} potencial={potPdvs}
          />

          <Alertas dados={alertas} carregando={lAlertas} />
        </div>
      )}
    </>
  )
}
