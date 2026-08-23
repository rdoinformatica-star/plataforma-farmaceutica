import { createBrowserRouter } from 'react-router-dom'

import { AppShell } from './components/AppShell'
import { ABC } from './pages/ABC'
import { Auditoria } from './pages/Auditoria'
import { CamposNovos } from './pages/CamposNovos'
import { Clientes } from './pages/Clientes'
import { Cobertura } from './pages/Cobertura'
import { Compra } from './pages/Compra'
import { Config } from './pages/Config'
import { Dashboard } from './pages/Dashboard'
import { Dimensoes } from './pages/Dimensoes'
import { Estoque } from './pages/Estoque'
import { Importacoes } from './pages/Importacoes'
import { Importar } from './pages/Importar'
import { Mapeamentos } from './pages/Mapeamentos'
import { Mercado } from './pages/Mercado'
import { Mix } from './pages/Mix'
import { Oportunidades } from './pages/Oportunidades'
import { Preco } from './pages/Preco'
import { Perfil } from './pages/Perfil'
import { ProgressoImport } from './pages/ProgressoImport'
import { VisaoGeral } from './pages/VisaoGeral'

export const rotas = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <VisaoGeral /> },
      { path: 'dashboard', element: <Dashboard /> },
      { path: 'abc', element: <ABC /> },
      { path: 'cobertura', element: <Cobertura /> },
      { path: 'mix', element: <Mix /> },
      { path: 'oportunidades', element: <Oportunidades /> },
      { path: 'estoque', element: <Estoque /> },
      { path: 'compra', element: <Compra /> },
      { path: 'mercado', element: <Mercado /> },
      { path: 'preco', element: <Preco /> },
      { path: 'importar', element: <Importar /> },
      { path: 'importacoes', element: <Importacoes /> },
      { path: 'importacoes/:id', element: <ProgressoImport /> },
      { path: 'importacoes/:id/perfil', element: <Perfil /> },
      { path: 'campos', element: <CamposNovos /> },
      { path: 'mapeamentos', element: <Mapeamentos /> },
      { path: 'dimensoes', element: <Dimensoes /> },
      { path: 'clientes', element: <Clientes /> },
      { path: 'auditoria', element: <Auditoria /> },
      { path: 'config', element: <Config /> },
    ],
  },
])
