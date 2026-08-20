import ReactECharts from 'echarts-for-react'
import { useMemo } from 'react'

/** Canvas nao entende var(--x) — ctx.fillStyle precisa da cor ja resolvida.
 * Todo componente que monta series/eixos do ECharts usa isto em vez de
 * escrever 'var(--wine)' direto numa opcao de cor. */
export function useCoresGrafico() {
  return useMemo(() => {
    const estilo = getComputedStyle(document.documentElement)
    const v = (nome: string, fallback: string) => estilo.getPropertyValue(nome).trim() || fallback
    return {
      ink: v('--ink', '#1b1416'),
      muted: v('--muted', '#6b5f62'),
      border: v('--border', '#e6dcdb'),
      borderForte: v('--border-strong', '#cfc0c0'),
      surface: v('--surface', '#ffffff'),
      wine: v('--wine', '#7a1420'),
      pos: v('--pos', '#0f6e4c'),
      neg: v('--neg', '#9c3d14'),
      mono: "'IBM Plex Mono', ui-monospace, monospace",
      sans: "'Public Sans', system-ui, sans-serif",
      categorica: ['--c1', '--c2', '--c3', '--c4', '--c5', '--c6', '--c7', '--c8']
        .map((nome) => v(nome, '#7a1420')),
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [document.documentElement.getAttribute('data-theme')])
}

/** Wrapper fino sobre ECharts com os tokens visuais do sistema — evita
 * repetir a mesma paleta/tipografia em cada grafico novo. */
export function Grafico({ opcoes, altura = 280 }: { opcoes: Record<string, unknown>; altura?: number }) {
  const cor = useCoresGrafico()

  const base = {
    color: cor.categorica,
    textStyle: { fontFamily: cor.sans, color: cor.ink },
    grid: { left: 48, right: 16, top: 16, bottom: 32 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: cor.surface,
      borderColor: cor.border,
      textStyle: { fontFamily: cor.mono, color: cor.ink, fontSize: 12 },
    },
    ...opcoes,
  }

  return <ReactECharts option={base} style={{ height: altura, width: '100%' }} notMerge />
}
