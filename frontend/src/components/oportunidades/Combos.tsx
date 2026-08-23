import { ComoFoiCalculado } from '../ComoFoiCalculado'
import { Aviso, Card, Kpi, Tag, Vazio } from '../ui'
import type { FocoCombo, SugestaoCombos } from '../../lib/analytics'
import { brl, inteiro } from '../../lib/format'

const FOCOS: { valor: FocoCombo; rotulo: string; ajuda: string }[] = [
  { valor: 'geral', rotulo: 'Geral',
    ajuda: 'Todos os pares que a base mostra andando juntos, sem olhar estoque.' },
  { valor: 'misto', rotulo: 'Pacote misto',
    ajuda: 'Puxador saudável + acompanhante parado: escoa capital sem só dar desconto.' },
  { valor: 'criticos', rotulo: 'Produtos críticos',
    ajuda: 'Acompanhantes com 180 a 365 dias de cobertura — ainda dá tempo de girar.' },
  { valor: 'zumbi', rotulo: 'Produtos zumbi',
    ajuda: 'Acompanhantes com mais de 365 dias de cobertura ou sem giro nenhum.' },
  { valor: 'giro_rapido', rotulo: 'Escoamento rápido',
    ajuda: 'Só produtos de giro alto dos dois lados — para volume, não para desova.' },
]

const CLASSE_TAG: Record<string, string> = {
  SAUDAVEL: 't-ok', ATENCAO: 't-hip', ALTO: 't-hip',
  CRITICO: 't-erro', ZUMBI: 't-erro', INDEFINIDO: 't-neutro',
}

function dias(v: number | null): string {
  if (v === null) return 'sem giro'
  return `${Math.round(v).toLocaleString('pt-BR')} d`
}

export function Combos({
  dados,
  foco,
  setFoco,
}: {
  dados: SugestaoCombos | undefined
  foco: FocoCombo
  setFoco: (f: FocoCombo) => void
}) {
  const ajudaFoco = FOCOS.find((f) => f.valor === foco)?.ajuda ?? ''

  return (
    <Card
      titulo="Sugestão de combos"
      acoes={
        <div className="linha" style={{ gap: 6, flexWrap: 'wrap' }}>
          {FOCOS.map((f) => (
            <button
              key={f.valor}
              className={foco === f.valor ? 'primario' : ''}
              onClick={() => setFoco(f.valor)}
              title={f.ajuda}
            >
              {f.rotulo}
            </button>
          ))}
          {dados?.disponivel && (
            <ComoFoiCalculado
              calculo={{
                titulo: 'Como os combos foram montados',
                formula: dados.calculo.formula,
                valores: Object.entries(dados.calculo.valores ?? {}).map(([rotulo, valor]) => ({
                  rotulo,
                  valor: String(valor),
                })),
                premissas: dados.calculo.premissas,
              }}
            />
          )}
        </div>
      }
    >
      {!dados ? (
        <div className="mut">Carregando...</div>
      ) : !dados.disponivel ? (
        <Vazio icone={null} titulo={dados.motivo} />
      ) : dados.itens.length === 0 ? (
        <Vazio icone={null} titulo="Nenhum combo passou nos critérios deste foco." />
      ) : (
        <div className="pilha" style={{ gap: 12 }}>
          <div className="mut" style={{ fontSize: 13 }}>{ajudaFoco}</div>

          <div className="kpis">
            <Kpi rotulo="Combos" valor={inteiro(dados.total)} />
            <Kpi
              rotulo="Capital parado alcançado"
              valor={brl(dados.capital_parado_alcancado)}
              sub="soma sem descontar repetição"
            />
          </div>

          <Aviso tipo="info">
            Os pares vêm de <b>co-ocorrência real</b>: são produtos que os mesmos PDVs
            já compram juntos no período. Isso não prova que um puxa o outro — pode ser
            o perfil da loja. O <b>lift</b> diz quantas vezes o par aparece junto acima
            do que o acaso explicaria. O mesmo acompanhante pode estar em vários combos,
            então o capital acima <b>não é soma limpa</b>.
          </Aviso>

          <div className="pilha" style={{ gap: 10 }}>
            {dados.itens.map((c) => (
              <div key={c.puxador_id} className="claim fato" style={{ margin: 0 }}>
                <div className="linha entre" style={{ alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ fontWeight: 700 }}>{c.puxador}</div>
                    <div className="mut" style={{ fontSize: 12, marginTop: 2 }}>
                      puxador · {inteiro(c.puxador_cobertura_pdvs)} PDVs já compram
                      {c.puxador_classe_estoque && (
                        <> · estoque {c.puxador_classe_estoque.toLowerCase()}</>
                      )}
                      {c.puxador_recorrencia != null && (
                        <> · recompra em {Math.round(c.puxador_recorrencia * 100)}% dos meses</>
                      )}
                    </div>
                  </div>
                  {c.capital_parado_no_combo > 0 && (
                    <div className="num" style={{ textAlign: 'right' }}>
                      <div style={{ fontWeight: 700 }}>{brl(c.capital_parado_no_combo)}</div>
                      <div className="mut" style={{ fontSize: 11 }}>parado no combo</div>
                    </div>
                  )}
                </div>

                <table style={{ marginTop: 8 }}>
                  <thead>
                    <tr>
                      <th>Levar junto</th>
                      <th className="num" title="Quantas vezes o par aparece junto acima do acaso">Lift</th>
                      <th className="num" title="Dos PDVs que compram o puxador, quantos já compram este">Conversão</th>
                      <th className="num">Cobertura</th>
                      <th>Estoque</th>
                      <th className="num">DDE</th>
                      <th className="num">Valor parado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {c.acompanhantes.map((a) => (
                      <tr key={a.produto_id}>
                        <td>
                          {a.produto}
                          {a.uso_continuo && (
                            <> <Tag tipo="t-ok">uso contínuo</Tag></>
                          )}
                        </td>
                        <td className="num" style={{ fontWeight: 600 }}>{a.lift.toFixed(1)}×</td>
                        <td className="num">{a.confianca_pct.toFixed(0)}%</td>
                        <td className="num">{inteiro(a.cobertura_pdvs)} PDVs</td>
                        <td>
                          {a.classe_estoque ? (
                            <Tag tipo={CLASSE_TAG[a.classe_estoque] ?? 't-neutro'}>
                              {a.classe_estoque}
                            </Tag>
                          ) : <span className="mut">—</span>}
                        </td>
                        <td className="num">{dias(a.dde)}</td>
                        <td className="num">{a.estoque_valor ? brl(a.estoque_valor) : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>

          {!dados.tem_estoque && (
            <Aviso tipo="atencao">
              Este cliente não tem arquivo de estoque importado, então os combos saem sem
              a camada de DDE e capital parado. Os focos que dependem de estoque
              (pacote misto, críticos, zumbi) ficam indisponíveis até a importação.
            </Aviso>
          )}
        </div>
      )}
    </Card>
  )
}
