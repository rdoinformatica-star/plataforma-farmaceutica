import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Boxes, Search } from 'lucide-react'
import { useState } from 'react'

import { Card, Carregando, Tag, Vazio } from '../components/ui'
import { api } from '../lib/api'

interface Produto {
  id: number
  nome_canonico: string
  ean: string | null
  marca: string | null
  eh_vitamedic: number
  eh_novo: number
}
interface Pdv {
  id: number
  razao_social: string
  cnpj: string | null
  uf: string | null
  cidade: string | null
  grupo: string | null
  eh_novo: number
}
interface Distribuidor {
  id: number
  nome: string
  cnpj: string | null
  uf: string | null
  eh_novo: number
}

const ABAS = [
  { valor: 'produtos', rotulo: 'Produtos' },
  { valor: 'pdvs', rotulo: 'Pontos de venda' },
  { valor: 'distribuidores', rotulo: 'Distribuidores' },
] as const
type TipoDim = (typeof ABAS)[number]['valor']

export function Dimensoes() {
  const [aba, setAba] = useState<TipoDim>('produtos')
  const [busca, setBusca] = useState('')
  const [soNovos, setSoNovos] = useState(false)
  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['dimensoes', aba, busca, soNovos],
    queryFn: () =>
      api.get<(Produto | Pdv | Distribuidor)[]>(
        `/dimensoes/${aba}?busca=${encodeURIComponent(busca)}${soNovos ? '&novo=true' : ''}&limite=200`,
      ),
  })

  const revisar = useMutation({
    mutationFn: (id: number) => api.post(`/dimensoes/${aba}/${id}/revisar`, { eh_novo: false }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['dimensoes'] }),
  })

  return (
    <>
      <header>
        <h1>Produtos e PDVs</h1>
        <p className="dek">
          Os cadastros que o sistema montou a partir das importações. Itens marcados como
          "novo" apareceram pela primeira vez e ainda não foram revisados.
        </p>
      </header>

      <Card
        acoes={
          <div className="linha" style={{ gap: 8 }}>
            <label className="linha" style={{ gap: 5, marginBottom: 0 }}>
              <input
                type="checkbox"
                style={{ width: 'auto' }}
                checked={soNovos}
                onChange={(e) => setSoNovos(e.target.checked)}
              />
              <span style={{ fontSize: 12, textTransform: 'none', letterSpacing: 0, fontWeight: 400 }}>
                só novos
              </span>
            </label>
            <div style={{ position: 'relative' }}>
              <Search size={14} style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)', color: 'var(--muted)' }} />
              <input
                placeholder="Buscar..."
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
                style={{ paddingLeft: 28, width: 200 }}
              />
            </div>
          </div>
        }
      >
        <div className="linha" style={{ gap: 6, marginBottom: 16, borderBottom: '1px solid var(--border)', paddingBottom: 12 }}>
          {ABAS.map((a) => (
            <button key={a.valor} className={aba === a.valor ? 'primario' : ''} onClick={() => setAba(a.valor)}>
              {a.rotulo}
            </button>
          ))}
        </div>

        {isLoading ? (
          <Carregando />
        ) : !data?.length ? (
          <Vazio icone={<Boxes size={36} />} titulo="Nada encontrado">
            {busca ? 'Tente outra busca.' : 'Importe dados para ver os cadastros aqui.'}
          </Vazio>
        ) : (
          <div className="rolagem">
            <table>
              <thead>
                <tr>
                  {aba === 'produtos' && (<><th>Produto</th><th>EAN</th><th>Marca</th></>)}
                  {aba === 'pdvs' && (<><th>Razão social</th><th>CNPJ</th><th>UF</th><th>Rede</th></>)}
                  {aba === 'distribuidores' && (<><th>Nome</th><th>CNPJ</th><th>UF</th></>)}
                  <th></th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.map((item: any) => (
                  <tr key={item.id}>
                    {aba === 'produtos' && (
                      <>
                        <td style={{ fontWeight: 600 }}>{item.nome_canonico}</td>
                        <td className="mut">{item.ean ?? '—'}</td>
                        <td className="mut">{item.marca ?? '—'}</td>
                      </>
                    )}
                    {aba === 'pdvs' && (
                      <>
                        <td style={{ fontWeight: 600 }}>{item.razao_social}</td>
                        <td className="mut">{item.cnpj ?? '—'}</td>
                        <td className="mut">{item.uf ?? '—'}</td>
                        <td className="mut">{item.grupo ?? '—'}</td>
                      </>
                    )}
                    {aba === 'distribuidores' && (
                      <>
                        <td style={{ fontWeight: 600 }}>{item.nome}</td>
                        <td className="mut">{item.cnpj ?? '—'}</td>
                        <td className="mut">{item.uf ?? '—'}</td>
                      </>
                    )}
                    <td>{!!item.eh_novo && <Tag tipo="t-novo">novo</Tag>}</td>
                    <td>
                      {!!item.eh_novo && (
                        <button className="discreto" onClick={() => revisar.mutate(item.id)}>
                          Marcar como revisado
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
