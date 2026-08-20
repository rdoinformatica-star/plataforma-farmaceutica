import { createBrowserRouter } from 'react-router-dom'

import { AppShell } from './components/AppShell'
import { Auditoria } from './pages/Auditoria'
import { CamposNovos } from './pages/CamposNovos'
import { Clientes } from './pages/Clientes'
import { Config } from './pages/Config'
import { Dimensoes } from './pages/Dimensoes'
import { Importacoes } from './pages/Importacoes'
import { Importar } from './pages/Importar'
import { Mapeamentos } from './pages/Mapeamentos'
import { Perfil } from './pages/Perfil'
import { ProgressoImport } from './pages/ProgressoImport'
import { VisaoGeral } from './pages/VisaoGeral'

export const rotas = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <VisaoGeral /> },
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
