import { useState } from 'react'

import { deInputMes, paraInputMes, resolverPreset, ROTULOS_PRESET, type PresetPeriodo, type Periodo } from '../../lib/periodo'

const PRESETS: PresetPeriodo[] = ['mes', 'trimestre', 'semestre', 'ano', 'tudo']

export function SeletorPeriodo({
  disponivel,
  valor,
  aoMudar,
}: {
  disponivel: Periodo
  valor: Periodo
  aoMudar: (p: Periodo) => void
}) {
  const [preset, setPreset] = useState<PresetPeriodo>('semestre')
  const [aberto, setAberto] = useState(false)

  function escolher(p: PresetPeriodo) {
    setPreset(p)
    if (p !== 'custom') {
      aoMudar(resolverPreset(p, disponivel))
      setAberto(false)
    } else {
      setAberto(true)
    }
  }

  return (
    <div className="linha" style={{ gap: 6, flexWrap: 'wrap' }}>
      {PRESETS.map((p) => (
        <button
          key={p}
          className={preset === p ? 'primario' : ''}
          onClick={() => escolher(p)}
        >
          {ROTULOS_PRESET[p]}
        </button>
      ))}
      <button className={preset === 'custom' ? 'primario' : ''} onClick={() => escolher('custom')}>
        Personalizado
      </button>
      {aberto && (
        <div className="linha" style={{ gap: 6 }}>
          <input
            type="month"
            min={paraInputMes(disponivel.ini)}
            max={paraInputMes(disponivel.fim)}
            value={paraInputMes(valor.ini)}
            onChange={(e) => aoMudar({ ...valor, ini: deInputMes(e.target.value) })}
            style={{ width: 150 }}
          />
          <span className="mut">até</span>
          <input
            type="month"
            min={paraInputMes(disponivel.ini)}
            max={paraInputMes(disponivel.fim)}
            value={paraInputMes(valor.fim)}
            onChange={(e) => aoMudar({ ...valor, fim: deInputMes(e.target.value) })}
            style={{ width: 150 }}
          />
        </div>
      )}
    </div>
  )
}
