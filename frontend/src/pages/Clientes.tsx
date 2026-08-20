import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Power, Search, Trash2, Users } from 'lucide-react'
import { useState } from 'react'

import { Card, Carregando, Drawer, FalhaAviso, Vazio } from '../components/ui'
import { api, FalhaApi, type Cliente } from '../lib/api'
import { dataHora, inteiro } from '../lib/format'
import { UFS } from '../lib/ufs'

type Rascunho = { nome: string; cnpj: string; uf_principal: string; grupo: string; observacoes: string }
const VAZIO: Rascunho = { nome: '', cnpj: '', uf_principal: '', grupo: '', observacoes: '' }

export function Clientes() {
  const qc = useQueryClient()
  const [busca, setBusca] = useState('')
  const [editando, setEditando] = useState<Cliente | null>(null)
  const [criando, setCriando] = useState(false)

  const { data: clientes, isLoading } = useQuery({
    queryKey: ['clientes', busca],
    queryFn: () => api.get<Cliente[]>(`/clientes?busca=${encodeURIComponent(busca)}`),
  })

  const desativar = useMutation({
    mutationFn: (id: number) => api.del(`/clientes/${id}?desativar=true`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['clientes'] }),
  })

  return (
    <>
      <header>
        <h1>Clientes</h1>
        <p className="dek">
          Cada cliente tem os próprios dados, fontes e histórico de importação —
          nada se mistura entre um distribuidor e outro.
        </p>
      </header>

      <Card
        titulo="Todos os clientes"
        acoes={
          <div className="linha" style={{ gap: 8 }}>
            <div style={{ position: 'relative' }}>
              <Search
                size={14}
                style={{
                  position: 'absolute',
                  left: 9,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--muted)',
                }}
              />
              <input
                placeholder="Buscar..."
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
                style={{ paddingLeft: 28, width: 200 }}
              />
            </div>
            <button className="primario" onClick={() => setCriando(true)}>
              <Plus size={15} />
              Novo cliente
            </button>
          </div>
        }
      >
        {isLoading ? (
          <Carregando />
        ) : !clientes?.length ? (
          <Vazio icone={<Users size={36} />} titulo="Nenhum cliente encontrado">
            {busca ? 'Tente outra busca.' : 'Cadastre o primeiro cliente para começar a importar dados.'}
          </Vazio>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Nome</th>
                <th>UF</th>
                <th className="num">Importações</th>
                <th>Última importação</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {clientes.map((c) => (
                <tr key={c.id} style={{ opacity: c.ativo ? 1 : 0.55 }}>
                  <td>
                    <a onClick={() => setEditando(c)} style={{ cursor: 'pointer', fontWeight: 600 }}>
                      {c.nome}
                    </a>
                    {!c.ativo && <span className="mut"> (inativo)</span>}
                  </td>
                  <td className="mut">{c.uf_principal ?? '—'}</td>
                  <td className="num">{inteiro(c.n_importacoes)}</td>
                  <td className="mut">{dataHora(c.ultima_importacao)}</td>
                  <td style={{ textAlign: 'right' }}>
                    {c.ativo && (
                      <button
                        className="discreto"
                        title="Desativar"
                        onClick={() => desativar.mutate(c.id)}
                      >
                        <Power size={14} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {criando && <FormularioCliente aoFechar={() => setCriando(false)} />}
      {editando && (
        <FormularioCliente cliente={editando} aoFechar={() => setEditando(null)} />
      )}
    </>
  )
}

function FormularioCliente({
  cliente,
  aoFechar,
}: {
  cliente?: Cliente
  aoFechar: () => void
}) {
  const qc = useQueryClient()
  const [d, setD] = useState<Rascunho>(
    cliente
      ? {
          nome: cliente.nome,
          cnpj: cliente.cnpj ?? '',
          uf_principal: cliente.uf_principal ?? '',
          grupo: cliente.grupo ?? '',
          observacoes: cliente.observacoes ?? '',
        }
      : VAZIO,
  )
  const [erro, setErro] = useState<FalhaApi | null>(null)

  const salvar = useMutation({
    mutationFn: () =>
      cliente ? api.put(`/clientes/${cliente.id}`, d) : api.post('/clientes', d),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['clientes'] })
      aoFechar()
    },
    onError: (e) => setErro(e instanceof FalhaApi ? e : null),
  })

  const excluir = useMutation({
    mutationFn: () => api.del(`/clientes/${cliente!.id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['clientes'] })
      aoFechar()
    },
    onError: (e) => setErro(e instanceof FalhaApi ? e : null),
  })

  return (
    <Drawer
      titulo={cliente ? 'Editar cliente' : 'Novo cliente'}
      aoFechar={aoFechar}
      rodape={
        <>
          {cliente && (
            <button className="perigo" onClick={() => excluir.mutate()}>
              <Trash2 size={14} />
              Excluir
            </button>
          )}
          <span style={{ flex: 1 }} />
          <button onClick={aoFechar}>Cancelar</button>
          <button
            className="primario"
            disabled={!d.nome.trim() || salvar.isPending}
            onClick={() => salvar.mutate()}
          >
            Salvar
          </button>
        </>
      }
    >
      {erro && <FalhaAviso erro={erro} />}
      <label>
        <span>Nome</span>
        <input
          value={d.nome}
          onChange={(e) => setD({ ...d, nome: e.target.value })}
          autoFocus
        />
      </label>
      <label>
        <span>UF principal</span>
        <select
          value={d.uf_principal}
          onChange={(e) => setD({ ...d, uf_principal: e.target.value })}
        >
          <option value="">—</option>
          {UFS.map((u) => (
            <option key={u} value={u}>
              {u}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>CNPJ</span>
        <input value={d.cnpj} onChange={(e) => setD({ ...d, cnpj: e.target.value })} />
      </label>
      <label>
        <span>Grupo / regional</span>
        <input value={d.grupo} onChange={(e) => setD({ ...d, grupo: e.target.value })} />
      </label>
      <label>
        <span>Observações</span>
        <textarea
          rows={3}
          value={d.observacoes}
          onChange={(e) => setD({ ...d, observacoes: e.target.value })}
        />
      </label>
    </Drawer>
  )
}
