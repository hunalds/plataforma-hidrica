import { ChartLine, PushPin, Table } from '@phosphor-icons/react'
import { useQuery } from '@tanstack/react-query'
import { lazy, Suspense, useMemo, useState } from 'react'

import { api, ApiError } from '../../api/client'
import { MODEL_LABELS, type Forecast, type Measurement } from '../../api/types'
import { Metric } from '../../components/status'
import { Alert, Card, Spinner } from '../../components/ui'
import { forecastAriaLabel, forecastOption } from '../../lib/forecastChart'
import { fmt } from '../../lib/format'

// ECharts se carga solo cuando hay una gráfica que mostrar (división del bundle)
const EChart = lazy(() => import('../../components/charts/EChart').then((m) => ({ default: m.EChart })))

const pct = (p: number) => `${Math.round(p * 100)} %`

function riskTone(p: number): string {
  if (p >= 0.5) return 'text-status-critical font-semibold'
  if (p >= 0.2) return 'text-status-alert font-semibold'
  return 'text-muted-foreground'
}

export function ForecastSection({ code }: { code: string }) {
  const [view, setView] = useState<'grafica' | 'tabla'>('grafica')
  const fq = useQuery({ queryKey: ['forecast', code], queryFn: () => api.get<Forecast>(`/reservoirs/${code}/forecast`), retry: false })
  const hq = useQuery({
    queryKey: ['measurements', code, 365],
    queryFn: () => api.get<Measurement[]>(`/reservoirs/${code}/measurements?limit=365`),
  })
  const option = useMemo(() => (fq.data && hq.data ? forecastOption(hq.data, fq.data) : null), [fq.data, hq.data])

  if (fq.isPending) return <Spinner label="Calculando la proyección…" />
  if (fq.isError) {
    const noModel = fq.error instanceof ApiError && fq.error.status === 404
    return (
      <Card>
        <h2 className="text-xl font-semibold">Proyección a 90 días</h2>
        <div className="mt-3">
          <Alert tone={noModel ? 'info' : 'error'}>{fq.error.message}</Alert>
        </div>
      </Card>
    )
  }
  const f = fq.data
  const lowProbs = f.probabilities.filter((p) => p.direction === 'bajo')

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Proyección a 90 días</h2>
          <p className="text-muted-foreground">
            Desde el último dato ({f.origin}). Modelo: {MODEL_LABELS[f.model.kind] ?? f.model.kind}
            {f.model.pinned && (
              <span className="ml-1 inline-flex items-center gap-1">
                <PushPin size={14} aria-hidden="true" /> fijado por el Ingeniero
              </span>
            )}
            {' · '}error medio en pruebas: {fmt(f.model.score_mae_hm3, 1)} hm³
          </p>
        </div>
        <div className="flex gap-1 rounded-md border border-border p-1" role="group" aria-label="Vista">
          {(['grafica', 'tabla'] as const).map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={view === v}
              onClick={() => setView(v)}
              className={`inline-flex min-h-9 cursor-pointer items-center gap-1 rounded px-3 text-sm font-semibold ${view === v ? 'bg-accent text-on-accent' : 'hover:bg-muted'}`}
            >
              {v === 'grafica' ? <ChartLine size={16} aria-hidden="true" /> : <Table size={16} aria-hidden="true" />}
              {v === 'grafica' ? 'Gráfica' : 'Tabla'}
            </button>
          ))}
        </div>
      </div>

      {view === 'grafica' && option && (
        <div className="mt-4">
          <Suspense fallback={<Spinner label="Cargando gráfica…" />}>
            <EChart option={option} label={forecastAriaLabel(f)} height={380} />
          </Suspense>
          <p className="mt-1 text-sm text-muted-foreground">
            La banda sombreada contiene el valor real 8 de cada 10 veces según las pruebas. Arrastra o usa la rueda para acercar.
          </p>
        </div>
      )}
      {view === 'tabla' && (
        <div className="mt-4 max-h-80 overflow-auto">
          <table className="w-full min-w-[480px] text-left text-sm">
            <caption className="sr-only">Proyección diaria de la cota</caption>
            <thead className="sticky top-0 border-b border-border bg-surface text-muted-foreground">
              <tr>
                <th scope="col" className="py-2 pr-3">Fecha</th>
                <th scope="col" className="py-2 pr-3 text-right">Mínimo probable (m)</th>
                <th scope="col" className="py-2 pr-3 text-right">Esperada (m)</th>
                <th scope="col" className="py-2 text-right">Máximo probable (m)</th>
              </tr>
            </thead>
            <tbody>
              {f.days.map((d) => (
                <tr key={d.day} className="border-b border-border last:border-0">
                  <td className="py-1 pr-3 tabular-nums">{d.day}</td>
                  <td className="py-1 pr-3 text-right tabular-nums">{fmt(d.level_p10)}</td>
                  <td className="py-1 pr-3 text-right font-semibold tabular-nums">{fmt(d.level_p50)}</td>
                  <td className="py-1 text-right tabular-nums">{fmt(d.level_p90)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        {f.horizons.map((h) => (
          <section key={h.horizon_days} className="rounded-lg border border-border p-4" aria-label={`En ${h.horizon_days} días`}>
            <h3 className="font-heading font-semibold">En {h.horizon_days} días · {h.date}</h3>
            <dl className="mt-3 grid grid-cols-2 gap-3">
              <Metric label="Cota esperada" value={`${fmt(h.level_p50)} m`} />
              <Metric label="Rango probable" value={`${fmt(h.level_p10)}–${fmt(h.level_p90)}`} />
              <Metric label="Volumen útil" value={`${fmt(h.useful_volume_p50, 1)} hm³`} />
              <Metric label="Disponibilidad" value={h.availability_pct_p50 !== null ? `${fmt(h.availability_pct_p50, 0)} %` : '—'} />
              <Metric label="Días de reserva" value={h.reserve_days_p50 !== null ? `${fmt(h.reserve_days_p50, 0)}` : '—'} />
              <Metric label="Prob. de alivio" value={pct(h.spill_probability)} />
            </dl>
          </section>
        ))}
      </div>

      {lowProbs.length > 0 && (
        <div className="mt-6">
          <h3 className="font-heading font-semibold">Probabilidad de bajar de cada umbral</h3>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[480px] text-left text-sm">
              <thead className="border-b border-border text-muted-foreground">
                <tr>
                  <th scope="col" className="py-2 pr-3">Umbral</th>
                  {[30, 60, 90].map((h) => (
                    <th key={h} scope="col" className="py-2 pr-3 text-right">
                      {h} días
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...new Set(lowProbs.map((p) => p.threshold))].map((t) => {
                  const rows = lowProbs.filter((p) => p.threshold === t)
                  return (
                    <tr key={t} className="border-b border-border last:border-0">
                      <td className="py-2 pr-3">
                        {rows[0].label} <span className="text-muted-foreground">({fmt(rows[0].level)} m)</span>
                      </td>
                      {[30, 60, 90].map((h) => {
                        const p = rows.find((r) => r.horizon_days === h)?.probability ?? 0
                        return (
                          <td key={h} className={`py-2 pr-3 text-right tabular-nums ${riskTone(p)}`}>
                            {pct(p)}
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {f.importance.length > 0 && (
        <div className="mt-6">
          <h3 className="font-heading font-semibold">¿Qué pesa más en la predicción?</h3>
          <ul className="mt-2 space-y-2">
            {f.importance.slice(0, 6).map((i) => (
              <li key={i.variable} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 text-sm sm:grid-cols-[16rem_minmax(0,1fr)_3rem]">
                <span>{i.descripcion}</span>
                <span className="hidden h-2 overflow-hidden rounded-full bg-muted sm:block" aria-hidden="true">
                  <span className="block h-full rounded-full bg-accent" style={{ width: `${Math.round(i.peso * 100 / f.importance[0].peso)}%` }} />
                </span>
                <span className="text-right tabular-nums text-muted-foreground">{pct(i.peso)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="mt-4 text-xs text-muted-foreground">Fuente de datos del modelo: {f.model.data_source}.</p>
    </Card>
  )
}
