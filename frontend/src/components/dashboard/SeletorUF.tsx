import type { AnaliseUF } from '../../lib/analytics'

/** Seletor de estado compartilhado pelas telas de análise.
 *
 * A lista de UFs vem do próprio recorte do cliente (analise_uf), não de uma
 * constante com os 27 estados: mostrar um estado onde ele não vende só produz
 * tela vazia. Some por inteiro quando o cliente não tem UF resolvida. */
export function SeletorUF({
  ufs,
  valor,
  aoMudar,
  rotulo = 'Estado',
  largura = 130,
}: {
  ufs: AnaliseUF | undefined
  valor: string | undefined
  aoMudar: (uf: string | undefined) => void
  rotulo?: string
  largura?: number
}) {
  if (!ufs?.disponivel || !ufs.itens.length) return null
  return (
    <label style={{ width: largura, marginBottom: 0 }}>
      <span>{rotulo}</span>
      <select value={valor ?? ''} onChange={(e) => aoMudar(e.target.value || undefined)}>
        <option value="">Todos</option>
        {ufs.itens.map((u) => (
          <option key={u.uf} value={u.uf}>{u.uf}</option>
        ))}
      </select>
    </label>
  )
}
