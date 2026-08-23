import { ComoFoiCalculado } from '../ComoFoiCalculado'
import { Th, useOrdenacao } from '../Tabela'
import { Aviso, Card, Kpi, Tag, Vazio } from '../ui'
import type { AjustePreco as TipoAjuste } from '../../lib/analytics'
import { brl, inteiro, pct } from '../../lib/format'

const PRIORIDADE_TAG: Record<string, string> = {
  ALTA: 't-erro', MEDIA: 't-hip', BAIXA: 't-neutro',
}
const CLASSE_TAG: Record<string, string> = {
  SAUDAVEL: 't-ok', ATENCAO: 't-hip', ALTO: 't-hip',
  CRITICO: 't-erro', ZUMBI: 't-erro', INDEFINIDO: 't-neutro',
}

export function AjustePreco({ dados }: { dados: TipoAjuste | undefined }) {
  const { itens, ordem, alternar } = useOrdenacao(dados?.disponivel ? dados.itens : [])

  return (
    <Card
      titulo="Ajuste de preço sugerido"
      acoes={
        dados?.disponivel ? (
          <ComoFoiCalculado
            calculo={{
              titulo: 'Como o ajuste foi calculado',
              formula: dados.calculo.formula,
              valores: Object.entries(dados.calculo.valores ?? {}).map(([rotulo, valor]) => ({
                rotulo,
                valor: String(valor),
              })),
              premissas: dados.calculo.premissas,
            }}
          />
        ) : undefined
      }
    >
      {!dados ? (
        <div className="mut">Carregando...</div>
      ) : !dados.disponivel ? (
        <Vazio icone={null} titulo={dados.motivo} />
      ) : itens.length === 0 ? (
        <Vazio
          icone={null}
          titulo="Nenhum produto acima do preço dos outros distribuidores."
        >
          Nada a ajustar neste recorte — o cliente está competitivo em preço.
        </Vazio>
      ) : (
        <div className="pilha" style={{ gap: 10 }}>
          <div className="kpis">
            <Kpi rotulo="Produtos acima do mercado" valor={inteiro(dados.n_produtos)} />
            <Kpi
              rotulo="Receita cedida se ajustar tudo"
              valor={brl(dados.receita_cedida_total)}
              sub="no volume atual, se nada mais mudar"
            />
            <Kpi
              rotulo="Sem volume para comparar"
              valor={inteiro(dados.n_sem_volume)}
              sub="média de preço não confiável"
            />
          </div>

          <Aviso tipo="atencao">
            A <b>receita cedida</b> assume que o volume não muda — é o custo do ajuste no
            pior cenário, não uma projeção. O objetivo do ajuste é justamente mudar o
            volume. Preço médio aqui é faturamento ÷ unidades: mistura condição
            comercial, bonificação e mix de embalagem, não é tabela de preço.
            Prioridade <b>ALTA</b> marca produto caro <i>e</i> com estoque parado — ali
            o ajuste ataca dois problemas de uma vez.
          </Aviso>

          <div className="rolagem">
            <table>
              <thead>
                <tr>
                  <Th campo="produto" ordem={ordem} alternar={alternar}>Produto</Th>
                  <Th campo="prioridade" ordem={ordem} alternar={alternar}>Prioridade</Th>
                  <Th campo="preco_cliente" ordem={ordem} alternar={alternar} num>Preço atual</Th>
                  <Th campo="preco_outros" ordem={ordem} alternar={alternar} num>Outros distrib.</Th>
                  <Th campo="diferenca_pct" ordem={ordem} alternar={alternar} num>Diferença</Th>
                  <Th campo="ajuste_sugerido_pct" ordem={ordem} alternar={alternar} num>Ajuste</Th>
                  <Th campo="classe_estoque" ordem={ordem} alternar={alternar}>Estoque</Th>
                  <Th campo="receita_cedida_no_volume_atual" ordem={ordem} alternar={alternar} num>
                    Receita cedida
                  </Th>
                </tr>
              </thead>
              <tbody>
                {itens.map((i) => (
                  <tr key={i.produto_id}>
                    <td>{i.produto}</td>
                    <td>
                      <Tag tipo={PRIORIDADE_TAG[i.prioridade] ?? 't-neutro'}>
                        {i.prioridade}
                      </Tag>
                    </td>
                    <td className="num">{brl(i.preco_cliente)}</td>
                    <td className="num">{brl(i.preco_outros)}</td>
                    <td className="num neg">+{pct(i.diferenca_pct)}</td>
                    <td className="num" style={{ fontWeight: 700 }}>
                      {i.ajuste_sugerido_pct.toFixed(1)}%
                    </td>
                    <td>
                      {i.classe_estoque ? (
                        <Tag tipo={CLASSE_TAG[i.classe_estoque] ?? 't-neutro'}>
                          {i.classe_estoque}
                        </Tag>
                      ) : <span className="mut">—</span>}
                    </td>
                    <td className="num">{brl(i.receita_cedida_no_volume_atual)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Card>
  )
}
