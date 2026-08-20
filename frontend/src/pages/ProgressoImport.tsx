import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, CheckCircle2, StopCircle } from 'lucide-react'
import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { Aviso, Barra, Card, Carregando, StatusImport } from '../components/ui'
import { api, type Importacao } from '../lib/api'
import { duracao, inteiro } from '../lib/format'

const ATIVAS = ['FILA', 'ABRINDO', 'PERFILANDO', 'DIMENSOES', 'CARREGANDO', 'INDEXANDO']

export function ProgressoImport() {
  const { id } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: imp, isLoading } = useQuery({
    queryKey: ['importacao', id],
    queryFn: () => api.get<Importacao>(`/importacoes/${id}`),
    refetchInterval: (q) =>
      ATIVAS.includes((q.state.data as Importacao | undefined)?.status ?? '') ? 800 : false,
    // Uma importacao grande leva minutos: se o usuario trocar de aba enquanto
    // espera, o progresso nao pode parecer travado quando ele voltar.
    refetchIntervalInBackground: true,
  })

  const cancelar = useMutation({
    mutationFn: () => api.post(`/importacoes/${id}/cancelar`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['importacao', id] }),
  })

  useEffect(() => {
    if (imp?.status === 'CONCLUIDO' && imp.tem_perfil) {
      const t = setTimeout(() => navigate(`/importacoes/${id}/perfil`), 900)
      return () => clearTimeout(t)
    }
  }, [imp?.status, imp?.tem_perfil, id, navigate])

  if (isLoading || !imp) return <Carregando />

  const ativa = ATIVAS.includes(imp.status)

  return (
    <>
      <header>
        <h1>{imp.arquivo_nome}</h1>
        <p className="dek">{imp.fonte_nome}{imp.cliente ? ` · ${imp.cliente}` : ''}</p>
      </header>

      <Card>
        <div className="pilha">
          <div className="linha entre">
            <StatusImport status={imp.status} />
            {ativa && (
              <button className="discreto" onClick={() => cancelar.mutate()}>
                <StopCircle size={14} />
                Cancelar
              </button>
            )}
          </div>

          {imp.status === 'FILA' && imp.posicao_na_fila ? (
            <Aviso tipo="info">
              Aguardando na fila — {imp.posicao_na_fila} importação(ões) na sua frente.
              O sistema processa uma de cada vez para não sobrecarregar o computador.
            </Aviso>
          ) : null}

          {ativa && (
            <div>
              <div className="linha entre" style={{ marginBottom: 8 }}>
                <span style={{ fontSize: 13 }}>{imp.etapa_atual}</span>
                <span className="num mut" style={{ fontSize: 12 }}>
                  {Math.round((imp.progresso ?? 0) * 100)}%
                  {imp.eta_seg != null && imp.eta_seg > 0 ? ` · faltam ~${duracao(imp.eta_seg)}` : ''}
                </span>
              </div>
              <Barra valor={imp.progresso ?? 0} />
              {imp.linhas_gravadas > 0 && (
                <div className="mut" style={{ fontSize: 12, marginTop: 6 }}>
                  {inteiro(imp.linhas_gravadas)} linhas gravadas até agora
                </div>
              )}
            </div>
          )}

          {imp.status === 'CONCLUIDO' && (
            <Aviso tipo="info">
              <CheckCircle2 size={14} style={{ verticalAlign: -2, marginRight: 4 }} />
              Concluída em {duracao(imp.duracao_seg)}. {inteiro(imp.linhas_gravadas)} registros
              gravados
              {imp.linhas_descartadas
                ? `, ${inteiro(imp.linhas_descartadas)} descartados`
                : ''}
              . Levando você para o perfil do dado...
            </Aviso>
          )}

          {imp.status === 'ERRO' && (
            <Aviso tipo="erro">
              <AlertCircle size={14} style={{ verticalAlign: -2, marginRight: 4 }} />
              <b>{imp.erro_mensagem}</b>
            </Aviso>
          )}

          {imp.status === 'CANCELADO' && (
            <Aviso tipo="atencao">Esta importação foi cancelada.</Aviso>
          )}

          {!!imp.log?.length && (
            <div>
              <div className="rot" style={{ marginBottom: 6 }}>Andamento</div>
              <div
                style={{
                  background: 'var(--surface-2)',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  padding: 10,
                  maxHeight: 260,
                  overflowY: 'auto',
                  fontFamily: 'var(--mono)',
                  fontSize: 11.5,
                }}
              >
                {imp.log.map((e, i) => (
                  <div
                    key={i}
                    style={{
                      color:
                        e.nivel === 'erro'
                          ? 'var(--neg)'
                          : e.nivel === 'aviso'
                            ? 'var(--warn)'
                            : e.nivel === 'motor'
                              ? 'var(--muted)'
                              : 'var(--ink-2)',
                      marginBottom: 2,
                    }}
                  >
                    <span style={{ opacity: 0.6 }}>{e.ts}</span> {e.texto}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </Card>
    </>
  )
}
