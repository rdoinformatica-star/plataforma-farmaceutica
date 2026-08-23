import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, KeyRound, ListChecks } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ComoFoiCalculado } from '../components/ComoFoiCalculado'
import { Aviso, Card, Carregando, Confianca, Drawer, Kpi, Tag } from '../components/ui'
import { api, type ColunaPerfil, type Perfil as TipoPerfil } from '../lib/api'
import { bytes, faixaPeriodo, inteiro, nomePapel, nomeProblema, pct } from '../lib/format'

export function Perfil() {
  const { id } = useParams()
  const [colunaAberta, setColunaAberta] = useState<ColunaPerfil | null>(null)

  const { data: p, isLoading } = useQuery({
    queryKey: ['perfil', id],
    queryFn: () => api.get<TipoPerfil>(`/importacoes/${id}/perfil`),
  })

  if (isLoading || !p) return <Carregando />

  const ds = p.dataset

  return (
    <>
      <header>
        <h1>Perfil do dado</h1>
        <p className="dek">
          {p.importacao.arquivo_nome} · {p.importacao.fonte_nome}
          {p.importacao.cliente ? ` · ${p.importacao.cliente}` : ''}
        </p>
      </header>

      <div className="pilha">
        <div className="kpis">
          <Kpi rotulo="Registros" valor={inteiro(ds.linhas_validas)} sub={
            ds.linhas_descartadas ? `${inteiro(ds.linhas_descartadas)} descartados` : 'nenhum descartado'
          } />
          <Kpi rotulo="Colunas" valor={inteiro(ds.colunas)} />
          <Kpi rotulo="Tamanho" valor={bytes(ds.bytes)} />
          {ds.periodo.min != null && (
            <Kpi rotulo="Período" valor={faixaPeriodo(ds.periodo.min, ds.periodo.max)} />
          )}
          {Object.entries(ds.entidades).slice(0, 2).map(([k, v]) => (
            <Kpi key={k} rotulo={k} valor={inteiro(v)} />
          ))}
        </div>

        {p.importacao.colunas_pendentes ? (
          <Aviso tipo="atencao">
            <b>
              {p.importacao.colunas_pendentes} campo
              {p.importacao.colunas_pendentes > 1 ? 's' : ''} novo
              {p.importacao.colunas_pendentes > 1 ? 's' : ''} nesta importação.
            </b>{' '}
            O sistema guardou os dados, mas precisa que você diga o que eles significam
            antes de usá-los em análise.{' '}
            <Link to="/campos">Decidir agora</Link>
          </Aviso>
        ) : null}

        {ds.motivo_descarte && (
          <Aviso tipo="info">
            {inteiro(ds.linhas_descartadas)} linha{ds.linhas_descartadas > 1 ? 's' : ''}{' '}
            descartada{ds.linhas_descartadas > 1 ? 's' : ''}: {ds.motivo_descarte}.
            {!!ds.amostras_descartadas.length && (
              <details style={{ marginTop: 6 }}>
                <summary style={{ cursor: 'pointer' }}>Ver exemplos</summary>
                <pre style={{ fontSize: 11, marginTop: 6 }}>
                  {JSON.stringify(ds.amostras_descartadas, null, 2)}
                </pre>
              </details>
            )}
          </Aviso>
        )}

        {ds.avisos.map((a, i) => (
          <Aviso key={i} tipo="atencao">{a}</Aviso>
        ))}

        {p.limitacoes.length > 0 && (
          <Card titulo="O que esta análise não responde">
            <div className="pilha" style={{ gap: 8 }}>
              {p.limitacoes.map((l, i) => (
                <div key={i} className="claim hipotese">
                  <p style={{ margin: 0 }}>{l}</p>
                </div>
              ))}
            </div>
          </Card>
        )}

        <Card
          titulo="Colunas"
          acoes={
            <span className="mut" style={{ fontSize: 12 }}>
              base: {ds.base_estatistica}
            </span>
          }
        >
          <div className="rolagem">
            <table>
              <thead>
                <tr>
                  <th>Coluna</th>
                  <th>Tipo</th>
                  <th>Papel identificado</th>
                  <th className="num">Confiança</th>
                  <th className="num">Nulos</th>
                  <th className="num">Distintos</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {p.colunas.map((c) => (
                  <tr key={c.ordem}>
                    <td style={{ fontWeight: 600 }}>{c.nome}</td>
                    <td className="mut">{c.tipo_inferido}</td>
                    <td>
                      <Tag tipo={c.papel.valor === 'DESCONHECIDO' ? 't-neutro' : 't-fato'}>
                        {nomePapel(c.papel.valor)}
                      </Tag>
                    </td>
                    <td className="num">
                      <Confianca valor={c.papel.confianca} />
                    </td>
                    <td className="num">{c.n_nulos ? pct(c.pct_nulos) : '—'}</td>
                    <td className="num">{inteiro(c.n_distintos)}</td>
                    <td>
                      <button className="discreto" onClick={() => setColunaAberta(c)}>
                        Detalhes
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {p.chaves_candidatas.length > 0 && (
          <Card titulo={<span><KeyRound size={14} style={{ verticalAlign: -2, marginRight: 6 }} />Chaves candidatas</span>}>
            <div className="pilha" style={{ gap: 8 }}>
              {p.chaves_candidatas.map((k, i) => (
                <div key={i} className="linha entre">
                  <span>{k.colunas.join(' + ')}</span>
                  <Tag tipo={k.unica ? 't-ok' : 't-neutro'}>
                    {k.unica ? 'única' : `${k.n_duplicatas} duplicatas`}
                  </Tag>
                </div>
              ))}
            </div>
          </Card>
        )}

        {p.duplicatas.linhas_integrais > 0 && (
          <Aviso tipo="atencao">
            <ListChecks size={14} style={{ verticalAlign: -2, marginRight: 4 }} />
            {inteiro(p.duplicatas.linhas_integrais)} linha(s) integralmente duplicada(s)
            encontrada(s) (base: {p.duplicatas.base}).
          </Aviso>
        )}

        {p.importacao.adaptador === 'html_tabular' && (
          <DossiesHtml importId={p.importacao.id} />
        )}

        <div className="linha entre">
          <ComoFoiCalculado
            calculo={{
              titulo: 'Como este perfil foi gerado',
              fonte: p.importacao.fonte_nome,
              arquivo: p.importacao.arquivo_nome,
              periodo: faixaPeriodo(ds.periodo.min, ds.periodo.max) ?? undefined,
              formula: 'Contagens exatas sobre a coluna inteira; distribuições caras usam ' +
                `amostra (${ds.base_estatistica}).`,
              valores: [
                { rotulo: 'Linhas lidas', valor: inteiro(ds.linhas_lidas) },
                { rotulo: 'Linhas válidas', valor: inteiro(ds.linhas_validas) },
                { rotulo: 'Linhas descartadas', valor: inteiro(ds.linhas_descartadas) },
                { rotulo: 'Tempo de análise', valor: `${ds.duracao_ms} ms` },
              ],
              premissas: [
                'Papel semântico de cada coluna é decidido por testes estruturais ' +
                  '(formato dos valores + nome), nunca por nome de arquivo ou cliente.',
                'Abaixo de 60% de confiança o papel fica como "não identificado" — ' +
                  'o sistema prefere admitir que não sabe a chutar.',
              ],
            }}
          />
        </div>
      </div>

      {colunaAberta && (
        <DetalheColuna coluna={colunaAberta} aoFechar={() => setColunaAberta(null)} />
      )}
    </>
  )
}

interface DossieTabela {
  id: number
  tabela_indice: number
  tabela_titulo: string | null
  cabecalhos: string[]
  linhas: string[][]
  distribuidor_nome_detectado: string | null
  distribuidor_vinculado: string | null
}

function DossiesHtml({ importId }: { importId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ['importacao', importId, 'dossies'],
    queryFn: () => api.get<DossieTabela[]>(`/importacoes/${importId}/dossies`),
  })

  if (isLoading) return <Carregando />
  if (!data?.length) return null

  const distribuidor = data[0]?.distribuidor_nome_detectado
  const vinculado = data[0]?.distribuidor_vinculado

  return (
    <Card
      titulo={`Tabelas de referência (${data.length})`}
      acoes={
        distribuidor ? (
          <Tag tipo={vinculado ? 't-ok' : 't-neutro'}>
            {vinculado
              ? `vinculado a ${vinculado}`
              : `"${distribuidor}" detectado — ainda sem cadastro`}
          </Tag>
        ) : undefined
      }
    >
      <Aviso tipo="info">
        Números já calculados no arquivo original (share, variação, penetração).
        Não entram no motor de ABC/cobertura/estoque/mercado — ficam aqui só para
        consulta.
      </Aviso>
      <div className="pilha" style={{ gap: 20, marginTop: 12 }}>
        {data.map((t) => (
          <div key={t.id}>
            <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>
              {t.tabela_titulo ?? `Tabela ${t.tabela_indice + 1}`}
            </div>
            <div className="rolagem">
              <table>
                <thead>
                  <tr>
                    {t.cabecalhos.map((h, i) => (
                      <th key={i} className={i > 0 ? 'num' : undefined}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {t.linhas.map((linha, i) => (
                    <tr key={i}>
                      {linha.map((v, j) => (
                        <td key={j} className={j > 0 ? 'num' : undefined}>{v}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}

function DetalheColuna({ coluna, aoFechar }: { coluna: ColunaPerfil; aoFechar: () => void }) {
  return (
    <Drawer titulo={coluna.nome} aoFechar={aoFechar}>
      <div className="pilha">
        <div>
          <div className="rot" style={{ marginBottom: 6 }}>Papel identificado</div>
          <div className="linha" style={{ gap: 8 }}>
            <Tag tipo={coluna.papel.valor === 'DESCONHECIDO' ? 't-neutro' : 't-fato'}>
              {nomePapel(coluna.papel.valor)}
            </Tag>
            <Confianca valor={coluna.papel.confianca} />
          </div>
          <p style={{ fontSize: 13, marginTop: 8 }}>{coluna.papel.evidencia}</p>
          {coluna.papel.alternativas.length > 0 && (
            <div className="mut" style={{ fontSize: 12 }}>
              Também considerado:{' '}
              {coluna.papel.alternativas.map((a) => `${nomePapel(a.valor)} (${Math.round(a.confianca * 100)}%)`).join(', ')}
            </div>
          )}
        </div>

        <div>
          <div className="rot" style={{ marginBottom: 6 }}>Estatísticas</div>
          <table>
            <tbody>
              <tr><td className="mut">Tipo bruto</td><td>{coluna.tipo_bruto}</td></tr>
              <tr><td className="mut">Nulos</td><td className="num">{inteiro(coluna.n_nulos)} ({pct(coluna.pct_nulos)})</td></tr>
              <tr><td className="mut">Valores distintos</td><td className="num">{inteiro(coluna.n_distintos)}</td></tr>
              {Object.entries(coluna.numerico).filter(([k]) => !['histograma'].includes(k)).map(([k, v]) => (
                <tr key={k}><td className="mut">{k}</td><td className="num">{String(v)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>

        {coluna.top.length > 0 && (
          <div>
            <div className="rot" style={{ marginBottom: 6 }}>Valores mais frequentes</div>
            <table>
              <tbody>
                {coluna.top.map((t) => (
                  <tr key={t.v}>
                    <td>{t.v}</td>
                    <td className="num">{inteiro(t.n)}</td>
                    <td className="num mut">{pct(t.pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {coluna.problemas.length > 0 && (
          <div>
            <div className="rot" style={{ marginBottom: 6 }}>Problemas encontrados</div>
            <div className="pilha" style={{ gap: 6 }}>
              {coluna.problemas.map((pb, i) => (
                <div key={i} className="aviso atencao" style={{ marginBottom: 0 }}>
                  <AlertTriangle size={14} />
                  <div>
                    <b>{nomeProblema(pb.tipo)}</b>
                    <div style={{ fontSize: 12.5 }}>{pb.detalhe}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {coluna.exemplos.length > 0 && (
          <div>
            <div className="rot" style={{ marginBottom: 6 }}>Exemplos</div>
            <div className="mut" style={{ fontSize: 12.5 }}>{coluna.exemplos.join(', ')}</div>
          </div>
        )}
      </div>
    </Drawer>
  )
}
