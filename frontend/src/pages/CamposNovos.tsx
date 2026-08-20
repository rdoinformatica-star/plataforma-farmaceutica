import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ClipboardCheck } from 'lucide-react'

import { Card, Carregando, Confianca, Tag, Vazio } from '../components/ui'
import { api, type ColunaImport } from '../lib/api'
import { nomePapel } from '../lib/format'

const OPCOES = [
  { valor: 'ARMAZENAR', rotulo: 'Guardar (fica disponível para análise)' },
  { valor: 'IGNORAR', rotulo: 'Ignorar (não guardar)' },
] as const

export function CamposNovos() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['colunas-pendentes'],
    queryFn: () => api.get<ColunaImport[]>('/colunas/pendentes'),
  })

  const decidir = useMutation({
    mutationFn: ({ id, decisao }: { id: number; decisao: string }) =>
      api.put(`/colunas/${id}/decisao`, { decisao }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['colunas-pendentes'] }),
  })

  return (
    <>
      <header>
        <h1>Campos novos</h1>
        <p className="dek">
          O sistema encontrou colunas que não reconheceu automaticamente. Elas já foram
          guardadas — nada foi descartado em silêncio — mas precisam da sua decisão antes
          de entrar em qualquer análise.
        </p>
      </header>

      <Card>
        {isLoading ? (
          <Carregando />
        ) : !data?.length ? (
          <Vazio icone={<ClipboardCheck size={36} />} titulo="Nada pendente">
            Todos os campos importados já foram revisados.
          </Vazio>
        ) : (
          <div className="pilha">
            {data.map((c) => (
              <div
                key={c.id}
                className="linha entre"
                style={{
                  padding: '12px 14px',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                }}
              >
                <div>
                  <div className="linha" style={{ gap: 8 }}>
                    <span style={{ fontWeight: 600 }}>{c.nome_original}</span>
                    <Tag tipo="t-novo">novo</Tag>
                  </div>
                  <div className="mut" style={{ fontSize: 12, marginTop: 3 }}>
                    {c.arquivo_nome} · {c.fonte} · sugestão: {nomePapel(c.papel_semantico)}{' '}
                    <Confianca valor={c.papel_confianca} />
                  </div>
                  <div className="mut" style={{ fontSize: 11.5, marginTop: 2 }}>
                    {c.papel_evidencia}
                  </div>
                </div>
                <div className="linha" style={{ gap: 6 }}>
                  {OPCOES.map((o) => (
                    <button
                      key={o.valor}
                      className={o.valor === 'ARMAZENAR' ? 'primario' : ''}
                      disabled={decidir.isPending}
                      onClick={() => decidir.mutate({ id: c.id, decisao: o.valor })}
                    >
                      {o.rotulo}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  )
}
