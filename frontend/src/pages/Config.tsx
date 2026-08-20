import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, XCircle } from 'lucide-react'

import { Card, Carregando } from '../components/ui'
import { api, type Saude } from '../lib/api'
import { bytes } from '../lib/format'

export function Config() {
  const { data: s, isLoading } = useQuery({
    queryKey: ['saude'],
    queryFn: () => api.get<Saude>('/health'),
  })

  if (isLoading || !s) return <Carregando />

  return (
    <>
      <header>
        <h1>Configurações</h1>
        <p className="dek">Estado do sistema e provedores de inteligência artificial.</p>
      </header>

      <div className="pilha">
        <Card titulo="Sistema">
          <table>
            <tbody>
              <tr><td className="mut">Versão</td><td>{s.versao} (Etapa {s.etapa})</td></tr>
              <tr><td className="mut">Python</td><td className="num">{s.python}</td></tr>
              <tr><td className="mut">SQLite</td><td className="num">{s.sqlite}</td></tr>
              <tr><td className="mut">Banco de dados</td><td className="num">{bytes(s.db_tamanho_mb * 1024 * 1024)}</td></tr>
              <tr><td className="mut">Tabelas</td><td className="num">{s.n_tabelas}</td></tr>
              <tr>
                <td className="mut">Motor de análise (engine/)</td>
                <td>
                  {s.engine_ok ? (
                    <span className="pos linha" style={{ gap: 5 }}>
                      <CheckCircle2 size={14} /> {s.engine_msg}
                    </span>
                  ) : (
                    <span className="neg linha" style={{ gap: 5 }}>
                      <XCircle size={14} /> {s.engine_msg}
                    </span>
                  )}
                </td>
              </tr>
            </tbody>
          </table>
        </Card>

        <Card
          titulo="Inteligência artificial"
        >
          <p className="mut" style={{ fontSize: 13, marginBottom: 14 }}>
            Todo cálculo quantitativo — somas, crescimento, participação, curva ABC — é
            feito localmente, sem IA. Nenhum provedor pago está ativo, e o sistema
            funciona por completo sem eles.
          </p>
          <table>
            <thead>
              <tr>
                <th>Provedor</th>
                <th>Status</th>
                <th>Observação</th>
              </tr>
            </thead>
            <tbody>
              {s.ia.map((p) => (
                <tr key={p.codigo}>
                  <td style={{ fontWeight: 600 }}>{p.rotulo}</td>
                  <td>
                    {p.disponivel ? (
                      <span className="pos">ativo</span>
                    ) : (
                      <span className="mut">não configurado</span>
                    )}
                  </td>
                  <td className="mut" style={{ fontSize: 12.5 }}>{p.observacao}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </>
  )
}
