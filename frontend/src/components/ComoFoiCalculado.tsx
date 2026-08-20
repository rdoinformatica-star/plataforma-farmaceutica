import { Calculator } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { Drawer } from './ui'

/**
 * Rastro de como um numero apareceu na tela.
 *
 * Na Etapa 1 mostra a procedencia da importacao (arquivo, sha, adaptador, o que
 * entrou e o que foi descartado). Da Etapa 2 em diante recebe tambem formula,
 * premissas e os valores usados — o contrato ja e este.
 */
export interface Calculo {
  titulo: string
  fonte?: string
  arquivo?: string
  sha256?: string
  periodo?: string | null
  campo?: string
  formula?: string
  premissas?: string[]
  valores?: { rotulo: string; valor: ReactNode }[]
  observacoes?: string[]
}

export function ComoFoiCalculado({ calculo }: { calculo: Calculo }) {
  const [aberto, setAberto] = useState(false)
  return (
    <>
      <button className="discreto" onClick={() => setAberto(true)}>
        <Calculator size={14} />
        Ver como foi calculado
      </button>
      {aberto && (
        <Drawer titulo={calculo.titulo} aoFechar={() => setAberto(false)}>
          <div className="pilha">
            {calculo.formula && (
              <div className="pull">
                <div className="rot">Fórmula</div>
                <div
                  className="num"
                  style={{ textAlign: 'left', marginTop: 6, fontSize: 14 }}
                >
                  {calculo.formula}
                </div>
              </div>
            )}

            {calculo.valores?.length ? (
              <div>
                <div className="rot" style={{ marginBottom: 8 }}>
                  Valores usados
                </div>
                <table>
                  <tbody>
                    {calculo.valores.map((v) => (
                      <tr key={v.rotulo}>
                        <td style={{ color: 'var(--muted)' }}>{v.rotulo}</td>
                        <td className="num">{v.valor}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}

            <div>
              <div className="rot" style={{ marginBottom: 8 }}>
                Procedência
              </div>
              <table>
                <tbody>
                  {calculo.fonte && (
                    <tr>
                      <td style={{ color: 'var(--muted)' }}>Fonte</td>
                      <td>{calculo.fonte}</td>
                    </tr>
                  )}
                  {calculo.arquivo && (
                    <tr>
                      <td style={{ color: 'var(--muted)' }}>Arquivo</td>
                      <td>{calculo.arquivo}</td>
                    </tr>
                  )}
                  {calculo.periodo && (
                    <tr>
                      <td style={{ color: 'var(--muted)' }}>Período</td>
                      <td>{calculo.periodo}</td>
                    </tr>
                  )}
                  {calculo.campo && (
                    <tr>
                      <td style={{ color: 'var(--muted)' }}>Campo</td>
                      <td>{calculo.campo}</td>
                    </tr>
                  )}
                  {calculo.sha256 && (
                    <tr>
                      <td style={{ color: 'var(--muted)' }}>Identificador</td>
                      <td
                        className="num"
                        style={{ textAlign: 'left', fontSize: 11, wordBreak: 'break-all' }}
                      >
                        {calculo.sha256}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {calculo.premissas?.length ? (
              <div>
                <div className="rot" style={{ marginBottom: 8 }}>
                  Premissas
                </div>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
                  {calculo.premissas.map((p, i) => (
                    <li key={i} style={{ marginBottom: 4 }}>
                      {p}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {calculo.observacoes?.length ? (
              <div>
                <div className="rot" style={{ marginBottom: 8 }}>
                  Observações
                </div>
                {calculo.observacoes.map((o, i) => (
                  <div key={i} className="claim">
                    <p style={{ marginTop: 0 }}>{o}</p>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </Drawer>
      )}
    </>
  )
}
