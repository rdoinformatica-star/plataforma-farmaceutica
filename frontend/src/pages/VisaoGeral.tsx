import { useQuery } from '@tanstack/react-query'
import { Database, Upload } from 'lucide-react'
import { Link } from 'react-router-dom'

import { ComoFoiCalculado } from '../components/ComoFoiCalculado'
import { Aviso, Card, Carregando, Kpi, StatusImport, Vazio } from '../components/ui'
import { api, type Estatisticas, type Importacao } from '../lib/api'
import { dataHora, inteiro, nomeElo } from '../lib/format'

export function VisaoGeral() {
  const { data: est, isLoading } = useQuery({
    queryKey: ['estatisticas'],
    queryFn: () => api.get<Estatisticas>('/estatisticas'),
  })
  const { data: importacoes } = useQuery({
    queryKey: ['importacoes', 'recentes'],
    queryFn: () => api.get<Importacao[]>('/importacoes?limite=10'),
    refetchInterval: (q) =>
      (q.state.data as Importacao[] | undefined)?.some((i) => i.em_andamento !== false &&
        !['CONCLUIDO', 'ERRO', 'CANCELADO'].includes(i.status))
        ? 1500
        : false,
    refetchIntervalInBackground: true,
  })

  if (isLoading || !est) return <Carregando />

  const vazio = est.importacoes === 0

  return (
    <>
      <header>
        <h1>Pharma Intelligence</h1>
        <p className="dek">
          Motor de inteligência comercial farmacêutica. Todo cálculo acontece aqui na sua
          máquina, sem custo de API e sem depender de internet.
        </p>
      </header>

      {vazio ? (
        <Card>
          <Vazio
            icone={<Database size={40} />}
            titulo="Nenhum dado importado ainda"
            acao={
              <Link to="/importar" className="btn primario">
                <Upload size={15} />
                Importar o primeiro arquivo
              </Link>
            }
          >
            Comece importando um relatório. O sistema vai reconhecer o formato, analisar as
            colunas e mostrar o que dá — e o que não dá — para responder com esses dados.
          </Vazio>
        </Card>
      ) : (
        <div className="pilha">
          <div className="kpis">
            <Kpi rotulo="Clientes" valor={inteiro(est.clientes)} />
            <Kpi rotulo="Importações" valor={inteiro(est.importacoes)} sub="concluídas" />
            <Kpi
              rotulo="Registros de venda"
              valor={inteiro(est.linhas_vendas)}
              sub="sell-out, grão bruto"
            />
            <Kpi rotulo="Produtos" valor={inteiro(est.produtos)} sub={
              est.produtos_novos ? `${est.produtos_novos} a revisar` : 'todos revisados'
            } />
            <Kpi rotulo="Pontos de venda" valor={inteiro(est.pdvs)} />
            <Kpi rotulo="Distribuidores" valor={inteiro(est.distribuidores)} />
          </div>

          {est.colunas_pendentes > 0 && (
            <Aviso tipo="atencao">
              <b>
                {est.colunas_pendentes} campo{est.colunas_pendentes > 1 ? 's' : ''} novo
                {est.colunas_pendentes > 1 ? 's' : ''} aguardando sua decisão.
              </b>{' '}
              O sistema guardou os dados, mas não vai usá-los em análise enquanto você não
              disser o que eles significam.{' '}
              <Link to="/campos">Revisar agora</Link>
            </Aviso>
          )}

          <div className="grade c2">
            <Card titulo="O que já entrou">
              <table>
                <thead>
                  <tr>
                    <th>Fonte</th>
                    <th>Elo da cadeia</th>
                    <th className="num">Importações</th>
                    <th className="num">Registros</th>
                  </tr>
                </thead>
                <tbody>
                  {est.por_fonte
                    .filter((f) => f.n_importacoes > 0)
                    .map((f) => (
                      <tr key={f.codigo}>
                        <td>{f.nome}</td>
                        <td className="mut">{eloDaFonte(f.codigo)}</td>
                        <td className="num">{inteiro(f.n_importacoes)}</td>
                        <td className="num">{inteiro(f.linhas)}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </Card>

            <Card
              titulo="Últimas importações"
              acoes={<Link to="/importacoes">Ver todas</Link>}
            >
              <table>
                <tbody>
                  {(importacoes ?? []).slice(0, 6).map((i) => (
                    <tr key={i.id}>
                      <td>
                        <Link to={`/importacoes/${i.id}`}>{i.arquivo_nome}</Link>
                        <div className="mut" style={{ fontSize: 11.5 }}>
                          {i.fonte_nome} · {dataHora(i.concluido_em ?? i.iniciado_em)}
                        </div>
                      </td>
                      <td style={{ width: 100 }}>
                        <StatusImport status={i.status} />
                      </td>
                      <td className="num" style={{ width: 90 }}>
                        {inteiro(i.linhas_gravadas)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </div>

          {est.ultima_importacao && (
            <Card titulo="Última importação">
              <div className="linha entre">
                <div>
                  <div className="rot">{est.ultima_importacao.fonte}</div>
                  <div style={{ fontWeight: 600, marginTop: 4 }}>
                    {est.ultima_importacao.arquivo_nome}
                  </div>
                  <div className="mut" style={{ fontSize: 12 }}>
                    {inteiro(est.ultima_importacao.linhas_gravadas)} registros ·{' '}
                    {dataHora(est.ultima_importacao.concluido_em)}
                  </div>
                </div>
                <ComoFoiCalculado
                  calculo={{
                    titulo: 'Procedência dos números acima',
                    fonte: est.ultima_importacao.fonte,
                    arquivo: est.ultima_importacao.arquivo_nome,
                    valores: [
                      { rotulo: 'Registros de venda', valor: inteiro(est.linhas_vendas) },
                      { rotulo: 'Linhas de estoque', valor: inteiro(est.linhas_estoque) },
                      { rotulo: 'Linhas de mercado', valor: inteiro(est.linhas_mercado) },
                      { rotulo: 'Produtos', valor: inteiro(est.produtos) },
                      { rotulo: 'Pontos de venda', valor: inteiro(est.pdvs) },
                    ],
                    premissas: [
                      'Só entram importações concluídas e marcadas como vigentes. ' +
                        'Reimportar um arquivo tira a versão anterior da conta, mas ' +
                        'não apaga o histórico.',
                    ],
                    observacoes: [
                      'Estes números contam registros importados. Não são análise ' +
                        'comercial — isso vem na próxima etapa.',
                    ],
                  }}
                />
              </div>
            </Card>
          )}
        </div>
      )}
    </>
  )
}

const ELOS: Record<string, string> = {
  SELLOUT: 'DISTRIBUIDOR_PDV',
  IQVIA: 'PDV_CONSUMIDOR',
  ESTOQUE: 'ESTOQUE',
  CADASTRO: 'CADASTRAL',
  PDVS: 'CADASTRAL',
}
const eloDaFonte = (codigo: string) => nomeElo(ELOS[codigo] ?? 'INDEFINIDO')
