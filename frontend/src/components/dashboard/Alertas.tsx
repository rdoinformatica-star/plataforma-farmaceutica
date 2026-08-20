import { Card, Carregando, Vazio } from '../ui'
import type { Alertas as TipoAlertas } from '../../lib/analytics'

const PONTO: Record<string, string> = {
  verde: 'var(--pos)',
  vermelho: 'var(--neg)',
  amarelo: 'var(--warn)',
  azul: 'var(--info)',
}

export function Alertas({ dados, carregando }: { dados: TipoAlertas | undefined; carregando: boolean }) {
  return (
    <Card titulo="Alertas de performance">
      {carregando || !dados ? (
        <Carregando />
      ) : !dados.disponivel ? (
        <div className="mut">{dados.motivo}</div>
      ) : !dados.itens.length ? (
        <Vazio icone={null} titulo="Nenhum alerta relevante neste período." />
      ) : (
        <div className="pilha" style={{ gap: 8 }}>
          {dados.itens.map((a, i) => (
            <div key={i} className="linha" style={{ gap: 10, fontSize: 13 }}>
              <span style={{
                width: 8, height: 8, borderRadius: '50%', flex: 'none',
                background: PONTO[a.tipo] ?? 'var(--muted)', marginTop: 5,
              }} />
              <span>{a.texto}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
