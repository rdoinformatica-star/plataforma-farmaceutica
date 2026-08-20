import { Card, Carregando, Tag, Vazio } from '../ui'
import type { VariacaoProdutos as TipoVariacao } from '../../lib/analytics'
import { brl, pct } from '../../lib/format'

const SELO: Record<string, { tipo: string; texto: string }> = {
  NOVO: { tipo: 't-novo', texto: 'novo' },
  CRESCIMENTO: { tipo: 't-fato', texto: 'crescimento' },
  ATENCAO: { tipo: 't-hip', texto: 'atenção' },
  QUEDA: { tipo: 't-erro', texto: 'queda' },
  QUEDA_CRITICA: { tipo: 't-erro', texto: 'queda crítica' },
}

export function VariacaoProdutos({
  titulo,
  dados,
  carregando,
}: {
  titulo: string
  dados: TipoVariacao | undefined
  carregando: boolean
}) {
  return (
    <Card titulo={titulo}>
      {carregando || !dados ? (
        <Carregando />
      ) : !dados.disponivel ? (
        <Vazio icone={null} titulo={dados.motivo} />
      ) : !dados.itens.length ? (
        <Vazio icone={null} titulo="Nenhum produto nesta faixa no período." />
      ) : (
        <div className="pilha" style={{ gap: 8 }}>
          {dados.itens.map((it) => {
            const selo = SELO[it.classificacao]
            return (
              <div key={it.produto_id} className="linha entre"
                   style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{it.produto}</div>
                  <div className="mut" style={{ fontSize: 11.5 }}>
                    {brl(it.faturamento_anterior)} → {brl(it.faturamento_atual)}
                  </div>
                </div>
                <div className="linha" style={{ gap: 8 }}>
                  <Tag tipo={selo.tipo}>{selo.texto}</Tag>
                  <span className={`num ${it.variacao_pct != null && it.variacao_pct >= 0 ? 'pos' : 'neg'}`}
                        style={{ fontWeight: 600 }}>
                    {it.variacao_pct == null ? 'novo' : `${it.variacao_pct >= 0 ? '+' : ''}${pct(it.variacao_pct)}`}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}
