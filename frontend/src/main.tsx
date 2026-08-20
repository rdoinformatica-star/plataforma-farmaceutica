import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'

import { rotas } from './router'
import { useEstado, aplicarTema } from './lib/estado'
import './styles/base.css'

aplicarTema(useEstado.getState().tema)

const cliente = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 5000 },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={cliente}>
      <RouterProvider router={rotas} />
    </QueryClientProvider>
  </StrictMode>,
)
