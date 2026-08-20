import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { History, Undo2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Card, Carregando, StatusImport, Tag, Vazio } from '../components/ui'
import { api, type Importacao } from '../lib/api'
import { dataHora, duracao, inteiro } from '../lib/format'

const ATIVAS = ['FILA', 'ABRINDO', 'PERFILANDO', 'DIMENSOES', 'CARREGANDO', 'INDEXANDO']

export function Importacoes() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['importacoes', 'todas'],
    queryFn: () => api.get<Importacao[]>('/importacoes?limite=200'),
    refetchInterval: (q) =>
      (q.state.data as Importacao[] | undefined)?.some((i) => ATIVAS.includes(i.status))
        ? 1500
        : false,
    refetchIntervalInBackground: true,
  })

  const desfazer = useMutation({
    mutationFn: (id: number) => api.post(`/importacoes/${id}/desfazer`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['importacoes'] }),
  })

  return (
    <>
      <header>
        <h1>Importações</h1>
        <p className="dek">
          Histórico completo. Reimportar um arquivo nunca apaga a versão anterior — ela
          só sai dos cálculos.
        </p>
      </header>

      <Card>
        {isLoading ? (
          <Carregando />
        ) : !data?.length ? (
          <Vazio icone={<History size={36} />} titulo="Nenhuma importação ainda">
            <Link to="/importar">Importe o primeiro arquivo</Link>
          </Vazio>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Arquivo</th>
                <th>Fonte</th>
                <th>Cliente</th>
                <th>Status</th>
                <th className="num">Registros</th>
                <th className="num">Duração</th>
                <th>Quando</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.map((i) => (
                <tr key={i.id} style={{ opacity: i.vigente ? 1 : 0.5 }}>
                  <td>
                    <Link to={ATIVAS.includes(i.status) ? `/importacoes/${i.id}` : `/importacoes/${i.id}/perfil`}>
                      {i.arquivo_nome}
                    </Link>
                    {!i.vigente && <Tag tipo="t-neutro">substituída</Tag>}
                  </td>
                  <td className="mut">{i.fonte_nome}</td>
                  <td className="mut">{i.cliente ?? '—'}</td>
                  <td><StatusImport status={i.status} /></td>
                  <td className="num">{inteiro(i.linhas_gravadas)}</td>
                  <td className="num mut">{duracao(i.duracao_seg)}</td>
                  <td className="mut">{dataHora(i.concluido_em ?? i.iniciado_em)}</td>
                  <td>
                    {i.status === 'CONCLUIDO' && (
                      <button
                        className="discreto"
                        title="Desfazer (remove os dados, mantém no histórico)"
                        onClick={() => {
                          if (confirm(`Remover os dados de "${i.arquivo_nome}"? O registro fica no histórico.`)) {
                            desfazer.mutate(i.id)
                          }
                        }}
                      >
                        <Undo2 size={14} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  )
}
