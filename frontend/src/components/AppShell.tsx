import { useQuery } from '@tanstack/react-query'
import {
  Boxes,
  ClipboardList,
  Database,
  History,
  LayoutDashboard,
  Link2,
  Monitor,
  Moon,
  PanelLeft,
  Settings,
  Sun,
  Upload,
  Users,
} from 'lucide-react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { api, type Estatisticas } from '../lib/api'
import { useEstado } from '../lib/estado'

const NAV = [
  {
    grupo: 'Painel',
    itens: [{ para: '/', rotulo: 'Visão geral', Icone: LayoutDashboard, fim: true }],
  },
  {
    grupo: 'Dados',
    itens: [
      { para: '/importar', rotulo: 'Importar dados', Icone: Upload },
      { para: '/importacoes', rotulo: 'Importações', Icone: History },
      { para: '/campos', rotulo: 'Campos novos', Icone: ClipboardList, contador: 'colunas_pendentes' },
      { para: '/mapeamentos', rotulo: 'Mapeamento de fontes', Icone: Link2 },
      { para: '/dimensoes', rotulo: 'Produtos e PDVs', Icone: Boxes, contador: 'produtos_novos' },
    ],
  },
  {
    grupo: 'Cadastro',
    itens: [{ para: '/clientes', rotulo: 'Clientes', Icone: Users }],
  },
  {
    grupo: 'Sistema',
    itens: [
      { para: '/auditoria', rotulo: 'Auditoria', Icone: Database },
      { para: '/config', rotulo: 'Configurações', Icone: Settings },
    ],
  },
] as const

const TITULOS: Record<string, string> = {
  '/': 'Visão geral',
  '/importar': 'Importar dados',
  '/importacoes': 'Importações',
  '/campos': 'Campos novos',
  '/mapeamentos': 'Mapeamento de fontes',
  '/dimensoes': 'Produtos e PDVs',
  '/clientes': 'Clientes',
  '/auditoria': 'Auditoria',
  '/config': 'Configurações',
}

function BotaoTema() {
  const { tema, setTema } = useEstado()
  const proximo = tema === 'auto' ? 'light' : tema === 'light' ? 'dark' : 'auto'
  const Icone = tema === 'auto' ? Monitor : tema === 'light' ? Sun : Moon
  const nome = tema === 'auto' ? 'automático' : tema === 'light' ? 'claro' : 'escuro'
  return (
    <button
      className="discreto"
      onClick={() => setTema(proximo)}
      title={`Tema ${nome} — clique para mudar`}
      aria-label={`Tema ${nome}`}
    >
      <Icone size={16} />
    </button>
  )
}

export function AppShell() {
  const { sidebarRecolhida, alternarSidebar } = useEstado()
  const local = useLocation()
  const { data: est } = useQuery({
    queryKey: ['estatisticas'],
    queryFn: () => api.get<Estatisticas>('/estatisticas'),
    refetchInterval: 15000,
  })

  const titulo =
    TITULOS[local.pathname] ??
    (local.pathname.startsWith('/importacoes') ? 'Importações' : 'Pharma Intelligence')

  return (
    <div className={`app ${sidebarRecolhida ? 'recolhida' : ''}`}>
      <aside className="sidebar">
        <div className="marca">
          <div className="sigla">PI</div>
          {!sidebarRecolhida && (
            <div className="nome">
              Pharma
              <br />
              Intelligence
              <small>Etapa 1</small>
            </div>
          )}
        </div>

        <nav>
          {NAV.map((g) => (
            <div key={g.grupo}>
              {!sidebarRecolhida && <div className="grupo">{g.grupo}</div>}
              {g.itens.map((i) => {
                const n = 'contador' in i && est ? (est[i.contador as keyof Estatisticas] as number) : 0
                return (
                  <NavLink
                    key={i.para}
                    to={i.para}
                    end={'fim' in i ? i.fim : false}
                    className={({ isActive }) => `item ${isActive ? 'ativo' : ''}`}
                    title={sidebarRecolhida ? i.rotulo : undefined}
                  >
                    <i.Icone size={16} />
                    {!sidebarRecolhida && <span>{i.rotulo}</span>}
                    {!sidebarRecolhida && n > 0 && <span className="selo">{n}</span>}
                  </NavLink>
                )
              })}
            </div>
          ))}
        </nav>

        {!sidebarRecolhida && (
          <div className="rodape">
            {est ? `${est.linhas_vendas.toLocaleString('pt-BR')} registros de venda` : '—'}
          </div>
        )}
      </aside>

      <div className="principal">
        <header className="topbar">
          <button
            className="discreto"
            onClick={alternarSidebar}
            aria-label="Recolher menu lateral"
          >
            <PanelLeft size={16} />
          </button>
          <span className="titulo">{titulo}</span>
          <span className="espaco" />
          <BotaoTema />
        </header>
        <main className="conteudo">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
