import { AlertTriangle, Info, Loader2, X, XCircle } from 'lucide-react'
import type { ReactNode } from 'react'

import type { FalhaApi } from '../lib/api'

export function Card({
  titulo,
  acoes,
  children,
  semCorpo,
}: {
  titulo?: ReactNode
  acoes?: ReactNode
  children: ReactNode
  semCorpo?: boolean
}) {
  return (
    <section className="card">
      {titulo && (
        <header>
          <h3>{titulo}</h3>
          {acoes && (
            <>
              <span style={{ flex: 1 }} />
              {acoes}
            </>
          )}
        </header>
      )}
      {semCorpo ? children : <div className="corpo">{children}</div>}
    </section>
  )
}

export function Kpi({
  rotulo,
  valor,
  sub,
  tom,
  titulo,
}: {
  rotulo: string
  valor: ReactNode
  sub?: ReactNode
  tom?: 'pos' | 'neg'
  titulo?: string
}) {
  return (
    <div className="kpi" title={titulo}>
      <div className="rot">{rotulo}</div>
      <div className={`val ${tom ?? ''}`}>{valor}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  )
}

export function Aviso({
  tipo = 'info',
  children,
}: {
  tipo?: 'info' | 'atencao' | 'erro'
  children: ReactNode
}) {
  const Icone = tipo === 'erro' ? XCircle : tipo === 'atencao' ? AlertTriangle : Info
  return (
    <div className={`aviso ${tipo}`}>
      <Icone size={16} />
      <div>{children}</div>
    </div>
  )
}

/** Erro da API traduzido pelo backend para portugues sem jargao. */
export function FalhaAviso({ erro }: { erro: FalhaApi }) {
  return (
    <Aviso tipo="erro">
      <b>{erro.erro.mensagem}</b>
      {erro.erro.detalhe && <div style={{ marginTop: 3 }}>{erro.erro.detalhe}</div>}
    </Aviso>
  )
}

export function Vazio({
  icone,
  titulo,
  children,
  acao,
}: {
  icone: ReactNode
  titulo: string
  children?: ReactNode
  acao?: ReactNode
}) {
  return (
    <div className="vazio">
      <div className="icone">{icone}</div>
      <h3>{titulo}</h3>
      {children && <p>{children}</p>}
      {acao}
    </div>
  )
}

export function Carregando({ texto = 'Carregando...' }: { texto?: string }) {
  return (
    <div className="vazio">
      <div className="icone">
        <Loader2 size={26} className="girando" />
      </div>
      <p style={{ margin: 0 }}>{texto}</p>
    </div>
  )
}

export function Barra({ valor }: { valor: number }) {
  return (
    <div className="barra">
      <div style={{ width: `${Math.round(Math.min(Math.max(valor, 0), 1) * 100)}%` }} />
    </div>
  )
}

export function Tag({
  tipo = 't-neutro',
  children,
}: {
  tipo?: string
  children: ReactNode
}) {
  return <span className={`tag ${tipo}`}>{children}</span>
}

const CLASSE_STATUS: Record<string, string> = {
  CONCLUIDO: 't-ok',
  ERRO: 't-erro',
  CANCELADO: 't-neutro',
}
const NOME_STATUS: Record<string, string> = {
  FILA: 'na fila',
  ABRINDO: 'abrindo',
  PERFILANDO: 'analisando',
  DIMENSOES: 'cadastrando',
  CARREGANDO: 'gravando',
  INDEXANDO: 'indexando',
  CONCLUIDO: 'concluída',
  ERRO: 'erro',
  CANCELADO: 'cancelada',
}

export function StatusImport({ status }: { status: string }) {
  return (
    <Tag tipo={CLASSE_STATUS[status] ?? 't-andamento'}>
      {NOME_STATUS[status] ?? status.toLowerCase()}
    </Tag>
  )
}

export function Drawer({
  titulo,
  aoFechar,
  rodape,
  children,
}: {
  titulo: ReactNode
  aoFechar: () => void
  rodape?: ReactNode
  children: ReactNode
}) {
  return (
    <>
      <div className="drawer-fundo" onClick={aoFechar} />
      <aside className="drawer" role="dialog" aria-modal="true">
        <header>
          <h2 style={{ flex: 1 }}>{titulo}</h2>
          <button className="discreto" onClick={aoFechar} aria-label="Fechar">
            <X size={18} />
          </button>
        </header>
        <div className="corpo">{children}</div>
        {rodape && <footer>{rodape}</footer>}
      </aside>
    </>
  )
}

/** Confiança da máquina, sempre visível: o usuário precisa poder discordar. */
export function Confianca({ valor }: { valor: number }) {
  const cor = valor >= 0.85 ? 'var(--pos)' : valor >= 0.6 ? 'var(--warn)' : 'var(--muted)'
  return (
    <span className="num" style={{ color: cor, fontSize: 11, fontWeight: 600 }}>
      {Math.round(valor * 100)}%
    </span>
  )
}
