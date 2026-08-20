/** Resolve presets de período (mês, trimestre, semestre, ano) para o par
 * periodo_ini/periodo_fim (AAAAMM) que a API espera. O backend não sabe o
 * que é "trimestre" — só recebe o intervalo já resolvido.
 */
export type PresetPeriodo = 'mes' | 'trimestre' | 'semestre' | 'ano' | 'tudo' | 'custom'

export interface Periodo {
  ini: number
  fim: number
}

function maisMeses(p: number, meses: number): number {
  const ano = Math.floor(p / 100)
  const mes = p % 100
  const total = ano * 12 + (mes - 1) + meses
  const ano2 = Math.floor(total / 12)
  const mes2 = ((total % 12) + 12) % 12
  return ano2 * 100 + (mes2 + 1)
}

/** Resolve um preset contra o intervalo disponível (min/max de dados do cliente). */
export function resolverPreset(preset: PresetPeriodo, disponivel: Periodo): Periodo {
  const fim = disponivel.fim
  switch (preset) {
    case 'mes':
      return { ini: fim, fim }
    case 'trimestre':
      return { ini: Math.max(maisMeses(fim, -2), disponivel.ini), fim }
    case 'semestre':
      return { ini: Math.max(maisMeses(fim, -5), disponivel.ini), fim }
    case 'ano':
      return { ini: Math.max(maisMeses(fim, -11), disponivel.ini), fim }
    case 'tudo':
      return { ...disponivel }
    default:
      return { ini: Math.max(maisMeses(fim, -6), disponivel.ini), fim }
  }
}

export const ROTULOS_PRESET: Record<PresetPeriodo, string> = {
  mes: 'Último mês',
  trimestre: 'Último trimestre',
  semestre: 'Último semestre',
  ano: 'Último ano',
  tudo: 'Tudo',
  custom: 'Personalizado',
}

/** AAAAMM <-> <input type="month"> (AAAA-MM). */
export const paraInputMes = (p: number) => `${String(p).slice(0, 4)}-${String(p).slice(4)}`
export const deInputMes = (v: string) => Number(v.replace('-', ''))
