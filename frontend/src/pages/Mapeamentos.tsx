import { useQuery } from '@tanstack/react-query'
import { Link2 } from 'lucide-react'
import { useState } from 'react'

import { Card, Carregando, Confianca, Tag, Vazio } from '../components/ui'
import { api } from '../lib/api'

interface Mapeamento {
  id: number
  entidade: string
  texto_origem: string
  entity_id: number
  metodo: string
  confianca: number | null
  status: string
  fonte: string
}

const ABAS = [
  { valor: 'PRODUTO', rotulo: 'Produtos' },
  { valor: 'PDV', rotulo: 'Pontos de venda' },
  { valor: 'DISTRIBUIDOR', rotulo: 'Distribuidores' },
] as const

export function Mapeamentos() {
  const [entidade, setEntidade] = useState<string>('PRODUTO')
  const { data, isLoading } = useQuery({
    queryKey: ['mapeamentos', entidade],
    queryFn: () => api.get<Mapeamento[]>(`/mapeamentos?entidade=${entidade}`),
  })

  return (
    <>
      <header>
        <h1>Mapeamento de fontes</h1>
        <p className="dek">
          Duas bases às vezes chamam o mesmo produto ou PDV de nomes diferentes. Aqui você
          confirma quando dois identificadores são a mesma coisa — o sistema nunca casa
          por preço ou por valor, só por texto.
        </p>
      </header>

      <Card
        titulo="Mapeamentos"
        acoes={
          <div className="linha" style={{ gap: 6 }}>
            {ABAS.map((a) => (
              <button
                key={a.valor}
                className={entidade === a.valor ? 'primario' : ''}
                onClick={() => setEntidade(a.valor)}
              >
                {a.rotulo}
              </button>
            ))}
          </div>
        }
      >
        {isLoading ? (
          <Carregando />
        ) : !data?.length ? (
          <Vazio icone={<Link2 size={36} />} titulo="Nenhum mapeamento ainda">
            Mapeamentos aparecem aqui conforme o sistema cruza fontes diferentes — por
            exemplo, quando um produto do IQVIA é ligado a um produto do sell-out.
          </Vazio>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Texto na origem</th>
                <th>Fonte</th>
                <th>Método</th>
                <th className="num">Confiança</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.map((m) => (
                <tr key={m.id}>
                  <td>{m.texto_origem}</td>
                  <td className="mut">{m.fonte}</td>
                  <td className="mut">{m.metodo}</td>
                  <td className="num">{m.confianca != null ? <Confianca valor={m.confianca} /> : '—'}</td>
                  <td>
                    <Tag tipo={m.status === 'ATIVO' ? 't-ok' : m.status === 'PENDENTE' ? 't-hip' : 't-neutro'}>
                      {m.status.toLowerCase()}
                    </Tag>
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
