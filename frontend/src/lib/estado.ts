import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Tema = 'auto' | 'light' | 'dark'

interface Estado {
  tema: Tema
  sidebarRecolhida: boolean
  clienteAtual: number | null
  setTema: (t: Tema) => void
  alternarSidebar: () => void
  setClienteAtual: (id: number | null) => void
}

export function aplicarTema(t: Tema) {
  const raiz = document.documentElement
  if (t === 'auto') {
    raiz.removeAttribute('data-theme')
    localStorage.removeItem('pharma-tema')
  } else {
    raiz.setAttribute('data-theme', t)
    // Chave simples, lida pelo script do index.html antes da primeira pintura.
    // Sem ela a tela pisca clara antes do React montar.
    localStorage.setItem('pharma-tema', t)
  }
}

export const useEstado = create<Estado>()(
  persist(
    (set) => ({
      tema: 'auto',
      sidebarRecolhida: false,
      clienteAtual: null,
      setTema: (tema) => {
        aplicarTema(tema)
        set({ tema })
      },
      alternarSidebar: () => set((s) => ({ sidebarRecolhida: !s.sidebarRecolhida })),
      setClienteAtual: (clienteAtual) => set({ clienteAtual }),
    }),
    { name: 'pharma-ui' },
  ),
)
