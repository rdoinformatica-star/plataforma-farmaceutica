import { useQuery } from '@tanstack/react-query'
import { Database } from 'lucide-react'

import { Card, Carregando, Vazio } from '../components/ui'
import { api } from '../lib/api'
import { dataHora } from '../lib/format'

interface Entrada {
  id: number
  ts: string
  ator: string
  acao: string
  entidade: string | null
  resumo: string
  detalhe: Record<string, unknown> | null
}

export function Auditoria() {
  const { data, isLoading } = useQuery({
    queryKey: ['auditoria'],
    queryFn: () => api.get<{ itens: Entrada[]; total: number }>('/auditoria?limite=200'),
  })

  return (
    <>
      <header>
        <h1>Auditoria</h1>
        <p className="dek">
          Todo evento que muda algo no sistema fica registrado aqui — quem, o quê e quando.
        </p>
      </header>

      <Card>
        {isLoading ? (
          <Carregando />
        ) : !data?.itens.length ? (
          <Vazio icone={<Database size={36} />} titulo="Nenhum evento registrado ainda" />
        ) : (
          <div className="pilha" style={{ gap: 0 }}>
            {data.itens.map((e, i) => (
              <div
                key={e.id}
                className="linha"
                style={{
                  gap: 14,
                  padding: '10px 0',
                  borderTop: i > 0 ? '1px solid var(--border)' : 'none',
                }}
              >
                <span className="mut num" style={{ fontSize: 11.5, width: 130, flex: 'none' }}>
                  {dataHora(e.ts)}
                </span>
                <span
                  className="mut"
                  style={{ fontSize: 10.5, width: 170, flex: 'none', fontFamily: 'var(--mono)' }}
                >
                  {e.acao}
                </span>
                <span style={{ fontSize: 13 }}>{e.resumo}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  )
}
