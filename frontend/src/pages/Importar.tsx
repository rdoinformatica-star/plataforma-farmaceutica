import { useMutation, useQuery } from '@tanstack/react-query'
import { CheckCircle2, File, FolderOpen, Upload, UploadCloud } from 'lucide-react'
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { Aviso, Card, Carregando, Confianca, FalhaAviso } from '../components/ui'
import {
  api,
  FalhaApi,
  type Candidato,
  type Cliente,
  type Deteccao,
  type Fonte,
  type ItemDisco,
} from '../lib/api'
import { bytes, dataHora } from '../lib/format'

type Origem = { tipo: 'DISCO'; caminho: string; nome: string; tamanho: number } |
             { tipo: 'UPLOAD'; sha256: string; nome: string; tamanho: number; caminho: string }

export function Importar() {
  const [passo, setPasso] = useState(1)
  const [origem, setOrigem] = useState<Origem | null>(null)
  const [deteccao, setDeteccao] = useState<Deteccao | null>(null)
  const [adaptador, setAdaptador] = useState<Candidato | null>(null)
  const [clienteId, setClienteId] = useState<number | ''>('')
  const [params, setParams] = useState<Record<string, unknown>>({})
  const navigate = useNavigate()

  const { data: clientes } = useQuery({
    queryKey: ['clientes'],
    queryFn: () => api.get<Cliente[]>('/clientes'),
  })
  const { data: fontes } = useQuery({
    queryKey: ['fontes'],
    queryFn: () => api.get<Fonte[]>('/fontes'),
  })

  const detectar = useMutation({
    mutationFn: (o: Origem) =>
      api.post<Deteccao>('/arquivos/detectar',
        o.tipo === 'DISCO'
          ? { origem: 'DISCO', caminho: o.caminho }
          : { origem: 'UPLOAD', sha256: o.sha256 }),
    onSuccess: (d) => {
      setDeteccao(d)
      setAdaptador(d.candidatos[0] ?? null)
      setParams(d.candidatos[0]?.params_sugeridos ?? {})
      setPasso(2)
    },
  })

  const importar = useMutation({
    mutationFn: (forcar: boolean) =>
      api.post<{ import_id: number }>('/importacoes', {
        origem: origem!.tipo,
        caminho: origem!.tipo === 'DISCO' ? origem!.caminho : undefined,
        sha256: origem!.tipo === 'UPLOAD' ? origem!.sha256 : undefined,
        adaptador: adaptador!.adaptador,
        client_id: clienteId || null,
        data_source_id: adaptador!.data_source_id,
        params,
        forcar_reimportacao: forcar,
        adaptador_forcado: adaptador!.adaptador !== deteccao!.candidatos[0]?.adaptador,
      }),
    onSuccess: (r) => navigate(`/importacoes/${r.import_id}`),
  })

  function escolher(o: Origem) {
    setOrigem(o)
    setDeteccao(null)
    detectar.mutate(o)
  }

  return (
    <>
      <header>
        <h1>Importar dados</h1>
        <p className="dek">
          O sistema reconhece o formato do arquivo, mostra o que entendeu e só grava
          depois da sua confirmação.
        </p>
      </header>

      <div className="pilha" style={{ maxWidth: 760 }}>
        <Passos atual={passo} />

        {passo === 1 && <PassoArquivo aoEscolher={escolher} detectando={detectar.isPending} />}

        {passo === 2 && deteccao && adaptador && (
          <PassoReconhecimento
            origem={origem!}
            deteccao={deteccao}
            adaptador={adaptador}
            setAdaptador={(c) => {
              setAdaptador(c)
              setParams(c.params_sugeridos)
            }}
            clienteId={clienteId}
            setClienteId={setClienteId}
            clientes={clientes ?? []}
            fontes={fontes ?? []}
            params={params}
            setParams={setParams}
            aoVoltar={() => setPasso(1)}
            aoConfirmar={(forcar) => importar.mutate(forcar)}
            importando={importar.isPending}
            erro={importar.error instanceof FalhaApi ? importar.error : null}
          />
        )}
      </div>
    </>
  )
}

function Passos({ atual }: { atual: number }) {
  const nomes = ['Arquivo', 'Reconhecimento', 'Processando', 'Perfil do dado']
  return (
    <div className="linha" style={{ gap: 6 }}>
      {nomes.map((n, i) => (
        <div
          key={n}
          className="linha"
          style={{
            gap: 6,
            fontSize: 12,
            fontWeight: i + 1 === atual ? 700 : 500,
            color: i + 1 <= atual ? 'var(--wine)' : 'var(--muted)',
          }}
        >
          <span
            style={{
              width: 20,
              height: 20,
              borderRadius: '50%',
              display: 'grid',
              placeItems: 'center',
              fontSize: 11,
              background: i + 1 <= atual ? 'var(--wine)' : 'var(--surface-2)',
              color: i + 1 <= atual ? '#fff' : 'var(--muted)',
              flex: 'none',
            }}
          >
            {i + 1 < atual ? <CheckCircle2 size={13} /> : i + 1}
          </span>
          {n}
          {i < nomes.length - 1 && (
            <span style={{ width: 24, height: 1, background: 'var(--border-strong)' }} />
          )}
        </div>
      ))}
    </div>
  )
}

function PassoArquivo({
  aoEscolher,
  detectando,
}: {
  aoEscolher: (o: Origem) => void
  detectando: boolean
}) {
  const [aba, setAba] = useState<'disco' | 'upload'>('disco')
  return (
    <Card semCorpo>
      <div className="linha" style={{ borderBottom: '1px solid var(--border)' }}>
        <AbaBtn ativo={aba === 'disco'} onClick={() => setAba('disco')}>
          <FolderOpen size={14} />
          Da pasta do projeto
        </AbaBtn>
        <AbaBtn ativo={aba === 'upload'} onClick={() => setAba('upload')}>
          <UploadCloud size={14} />
          Do computador
        </AbaBtn>
      </div>
      <div className="corpo">
        {detectando ? (
          <Carregando texto="Reconhecendo o arquivo..." />
        ) : aba === 'disco' ? (
          <NavegadorDisco aoEscolher={aoEscolher} />
        ) : (
          <UploadArea aoEscolher={aoEscolher} />
        )}
      </div>
    </Card>
  )
}

function AbaBtn({
  ativo,
  onClick,
  children,
}: {
  ativo: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      style={{
        flex: 1,
        borderRadius: 0,
        border: 'none',
        borderBottom: `2px solid ${ativo ? 'var(--wine)' : 'transparent'}`,
        background: 'transparent',
        color: ativo ? 'var(--wine)' : 'var(--muted)',
        justifyContent: 'center',
        padding: '12px 0',
      }}
    >
      {children}
    </button>
  )
}

function NavegadorDisco({ aoEscolher }: { aoEscolher: (o: Origem) => void }) {
  const [pasta, setPasta] = useState<string | undefined>(undefined)
  const { data, isLoading } = useQuery({
    queryKey: ['disco', pasta],
    queryFn: () => api.get<{ pasta: string; pai: string | null; itens: ItemDisco[] }>(
      `/arquivos/disco${pasta ? `?pasta=${encodeURIComponent(pasta)}` : ''}`,
    ),
  })

  if (isLoading || !data) return <Carregando />

  return (
    <div>
      <div className="mut" style={{ fontSize: 12, marginBottom: 10 }}>
        {data.pasta}
      </div>
      <table>
        <tbody>
          {data.pai && (
            <tr>
              <td colSpan={3}>
                <a onClick={() => setPasta(data.pai!)} style={{ cursor: 'pointer' }}>
                  .. (voltar)
                </a>
              </td>
            </tr>
          )}
          {data.itens.map((it) => (
            <tr key={it.caminho} style={{ opacity: it.tipo === 'arquivo' && !it.suportado ? 0.4 : 1 }}>
              <td style={{ width: 28 }}>
                {it.tipo === 'pasta' ? <FolderOpen size={15} /> : <File size={15} />}
              </td>
              <td>
                {it.tipo === 'pasta' ? (
                  <a onClick={() => setPasta(it.caminho)} style={{ cursor: 'pointer' }}>
                    {it.nome}
                  </a>
                ) : it.suportado ? (
                  <a
                    onClick={() =>
                      aoEscolher({
                        tipo: 'DISCO',
                        caminho: it.caminho,
                        nome: it.nome,
                        tamanho: it.bytes ?? 0,
                      })
                    }
                    style={{ cursor: 'pointer', fontWeight: 600 }}
                  >
                    {it.nome}
                  </a>
                ) : (
                  it.nome
                )}
              </td>
              <td className="num mut" style={{ width: 90 }}>
                {it.tipo === 'arquivo' ? bytes(it.bytes) : ''}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function UploadArea({ aoEscolher }: { aoEscolher: (o: Origem) => void }) {
  const ref = useRef<HTMLInputElement>(null)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<FalhaApi | null>(null)

  async function enviar(arquivo: File) {
    setEnviando(true)
    setErro(null)
    try {
      const r = await api.upload(arquivo)
      aoEscolher({ tipo: 'UPLOAD', sha256: r.sha256, nome: r.nome, tamanho: r.bytes, caminho: r.caminho })
    } catch (e) {
      if (e instanceof FalhaApi) setErro(e)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div>
      {erro && <FalhaAviso erro={erro} />}
      <Aviso tipo="info">
        Arquivos grandes (dashboards de sell-out e mercado) são mais rápidos pela aba
        "Da pasta do projeto" — evita reenviar dezenas de megabytes.
      </Aviso>
      <div
        onClick={() => ref.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault()
          const f = e.dataTransfer.files[0]
          if (f) enviar(f)
        }}
        style={{
          border: '2px dashed var(--border-strong)',
          borderRadius: 8,
          padding: 40,
          textAlign: 'center',
          cursor: 'pointer',
          color: 'var(--muted)',
        }}
      >
        {enviando ? (
          <Carregando texto="Enviando..." />
        ) : (
          <>
            <Upload size={28} style={{ marginBottom: 8 }} />
            <p style={{ margin: 0 }}>Arraste um arquivo aqui ou clique para escolher</p>
            <p className="mut" style={{ fontSize: 12, marginTop: 4 }}>
              .xlsx, .csv ou .html
            </p>
          </>
        )}
      </div>
      <input
        ref={ref}
        type="file"
        hidden
        accept=".xlsx,.xls,.csv,.txt,.html,.htm"
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) enviar(f)
        }}
      />
    </div>
  )
}

function PassoReconhecimento({
  origem,
  deteccao,
  adaptador,
  setAdaptador,
  clienteId,
  setClienteId,
  clientes,
  fontes,
  params,
  setParams,
  aoVoltar,
  aoConfirmar,
  importando,
  erro,
}: {
  origem: Origem
  deteccao: Deteccao
  adaptador: Candidato
  setAdaptador: (c: Candidato) => void
  clienteId: number | ''
  setClienteId: (v: number | '') => void
  clientes: Cliente[]
  fontes: Fonte[]
  params: Record<string, unknown>
  setParams: (p: Record<string, unknown>) => void
  aoVoltar: () => void
  aoConfirmar: (forcar: boolean) => void
  importando: boolean
  erro: FalhaApi | null
}) {
  const fonte = fontes.find((f) => f.id === adaptador.data_source_id)
  const jaImportado = deteccao.ja_importado

  return (
    <Card titulo="O que o sistema entendeu">
      <div className="pilha">
        <div>
          <div className="rot" style={{ marginBottom: 6 }}>Arquivo</div>
          <div style={{ fontWeight: 600 }}>{origem.nome}</div>
          <div className="mut" style={{ fontSize: 12 }}>{bytes(origem.tamanho)}</div>
        </div>

        {jaImportado && (
          <Aviso tipo="atencao">
            Este arquivo já foi importado em {dataHora(jaImportado.concluido_em)}, com{' '}
            {jaImportado.linhas_gravadas} registros. Importar de novo cria uma nova versão
            e substitui a anterior nos cálculos — o histórico não é apagado.
          </Aviso>
        )}

        <div>
          <div className="rot" style={{ marginBottom: 6 }}>Detectamos</div>
          <div className="pilha" style={{ gap: 6 }}>
            {deteccao.candidatos.map((c) => (
              <label
                key={c.adaptador}
                className="linha"
                style={{
                  gap: 10,
                  padding: '9px 12px',
                  border: `1px solid ${adaptador.adaptador === c.adaptador ? 'var(--wine)' : 'var(--border)'}`,
                  borderRadius: 6,
                  cursor: 'pointer',
                  background: adaptador.adaptador === c.adaptador ? 'var(--wine-soft)' : 'transparent',
                }}
              >
                <input
                  type="radio"
                  style={{ width: 'auto' }}
                  checked={adaptador.adaptador === c.adaptador}
                  onChange={() => setAdaptador(c)}
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{c.rotulo}</div>
                  <div className="mut" style={{ fontSize: 11.5 }}>{c.motivo}</div>
                </div>
                <Confianca valor={c.confianca} />
              </label>
            ))}
          </div>
        </div>

        <label>
          <span>Cliente (opcional)</span>
          <select
            value={clienteId}
            onChange={(e) => setClienteId(e.target.value ? Number(e.target.value) : '')}
          >
            <option value="">Sem cliente específico</option>
            {clientes.map((c) => (
              <option key={c.id} value={c.id}>{c.nome}</option>
            ))}
          </select>
        </label>

        {fonte?.aviso_elo && (
          <Aviso tipo="info">{fonte.aviso_elo}</Aviso>
        )}

        {'abas_disponiveis' in adaptador.params_sugeridos &&
          Array.isArray(adaptador.params_sugeridos.abas_disponiveis) && (
            <label>
              <span>Aba</span>
              <select
                value={String(params.aba ?? '')}
                onChange={(e) => setParams({ ...params, aba: e.target.value })}
              >
                {(adaptador.params_sugeridos.abas_disponiveis as string[]).map((a) => (
                  <option key={a} value={a}>{a}</option>
                ))}
              </select>
            </label>
        )}

        {erro && <FalhaAviso erro={erro} />}

        <div className="linha fim" style={{ gap: 8 }}>
          <button onClick={aoVoltar} disabled={importando}>Voltar</button>
          <button
            className="primario"
            disabled={importando}
            onClick={() => aoConfirmar(!!jaImportado)}
          >
            {importando ? 'Iniciando...' : jaImportado ? 'Importar mesmo assim' : 'Confirmar e importar'}
          </button>
        </div>
      </div>
    </Card>
  )
}
