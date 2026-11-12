import { useQuery } from '@tanstack/react-query'
import { lazy, Suspense, useMemo, useState } from 'react'
import { Link } from 'react-router'

import { api } from '../../api/client'
import { useReservoirs, useStatuses } from '../../api/reservoirs'
import type { ComparisonSeries, MapFeatures } from '../../api/types'
import { Alert, Card, EmptyState, PageHeader, Spinner } from '../../components/ui'
import { CHART, baseAxis } from '../../lib/chartTheme'
import { fmt } from '../../lib/format'
import { AlertsPanel } from '../alerts/AlertsPanel'
import { ReservoirCard } from '../reservoirs/ReservoirsPage'

const EChart = lazy(() => import('../../components/charts/EChart').then((m) => ({ default: m.EChart })))
const ReservoirMap = lazy(() => import('../../components/map/ReservoirMap').then((m) => ({ default: m.ReservoirMap })))

// Paleta categórica validada (dataviz): azul, naranja, aqua — en orden fijo por embalse, nunca por rango
const SERIES_COLOR: Record<string, string> = { TULE: '#2a78d6', MANUELOTE: '#eb6834', TRES_RIOS: '#1baf7a' }

function ComparisonChart() {
  const [view, setView] = useState<'grafica' | 'tabla'>('grafica')
  const q = useQuery({ queryKey: ['comparison'], queryFn: () => api.get<ComparisonSeries[]>('/dashboard/comparison?days=365') })
  const option = useMemo(
    () =>
      q.data && {
        animation: false,
        textStyle: { fontFamily: CHART.font },
        grid: { left: 48, right: 96, top: 32, bottom: 32 },
        legend: { top: 0, left: 0, textStyle: { color: CHART.textSecondary } },
        tooltip: { trigger: 'axis', valueFormatter: (v: unknown) => (typeof v === 'number' ? `${fmt(v, 1)} %` : '—') },
        xAxis: { type: 'time', ...baseAxis, splitLine: { show: false } },
        yAxis: { type: 'value', name: 'Disponibilidad (%)', nameTextStyle: { color: CHART.textSecondary }, min: 0, ...baseAxis },
        series: q.data.map((s) => ({
          name: s.name,
          type: 'line',
          data: s.availability,
          showSymbol: false,
          lineStyle: { width: 2, color: SERIES_COLOR[s.reservoir_code] },
          itemStyle: { color: SERIES_COLOR[s.reservoir_code] },
          // Rótulo directo al final: la identidad no depende solo del color
          endLabel: { show: true, formatter: '{a}', color: CHART.textPrimary, fontWeight: 600 },
          markLine:
            s.reservoir_code === q.data[0].reservoir_code
              ? { symbol: 'none', silent: true, lineStyle: { type: 'dashed', color: CHART.textSecondary }, label: { formatter: 'Nivel normal (100 %)', color: CHART.textSecondary }, data: [{ yAxis: 100 }] }
              : undefined,
        })),
      },
    [q.data],
  )
  if (q.isPending) return <Spinner label="Cargando comparativo…" />
  if (!q.data || q.data.every((s) => s.availability.length === 0)) return null
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Disponibilidad comparada (último año)</h2>
          <p className="text-muted-foreground">Volumen útil de cada embalse como porcentaje de su capacidad útil.</p>
        </div>
        <button type="button" className="min-h-11 cursor-pointer rounded-md border border-border px-3 font-semibold hover:bg-muted" onClick={() => setView(view === 'grafica' ? 'tabla' : 'grafica')}>
          {view === 'grafica' ? 'Ver como tabla' : 'Ver gráfica'}
        </button>
      </div>
      {view === 'grafica' && option ? (
        <Suspense fallback={<Spinner label="Cargando gráfica…" />}>
          <div className="mt-3">
            <EChart option={option} height={320} label={`Disponibilidad del último año: ${q.data.map((s) => `${s.name} ${fmt(s.availability.at(-1)?.[1] ?? null, 0)} %`).join(', ')}`} />
          </div>
        </Suspense>
      ) : (
        <table className="mt-3 w-full text-left text-sm">
          <caption className="sr-only">Disponibilidad reciente por embalse</caption>
          <thead className="border-b border-border text-muted-foreground">
            <tr>
              <th scope="col" className="py-2 pr-3">Embalse</th>
              <th scope="col" className="py-2 pr-3 text-right">Último valor</th>
              <th scope="col" className="py-2 pr-3 text-right">Mínimo del año</th>
              <th scope="col" className="py-2 text-right">Máximo del año</th>
            </tr>
          </thead>
          <tbody>
            {q.data.map((s) => {
              const vals = s.availability.map((p) => p[1])
              return (
                <tr key={s.reservoir_code} className="border-b border-border last:border-0">
                  <th scope="row" className="py-2 pr-3 text-left">{s.name}</th>
                  <td className="py-2 pr-3 text-right tabular-nums">{fmt(vals[vals.length - 1] ?? null, 1)} %</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{fmt(vals.length ? Math.min(...vals) : null, 1)} %</td>
                  <td className="py-2 text-right tabular-nums">{fmt(vals.length ? Math.max(...vals) : null, 1)} %</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </Card>
  )
}

export function MapCard({ height = 420 }: { height?: number }) {
  const q = useQuery({ queryKey: ['map'], queryFn: () => api.get<MapFeatures>('/map/features') })
  return (
    <Card>
      <h2 className="text-xl font-semibold">Mapa de los embalses</h2>
      <p className="mb-3 text-muted-foreground">Color según el semáforo. Toca un embalse para ver su resumen.</p>
      {q.isPending && <Spinner label="Cargando mapa…" />}
      {q.isError && <Alert tone="error">{q.error.message}</Alert>}
      {q.data && (
        <Suspense fallback={<Spinner label="Cargando mapa…" />}>
          <ReservoirMap data={q.data} height={height} />
        </Suspense>
      )}
    </Card>
  )
}

export function DashboardPage() {
  const reservoirs = useReservoirs()
  const statuses = useStatuses()
  const byCode = new Map(statuses.data?.map((s) => [s.reservoir_code, s]))
  const lastDay = statuses.data?.map((s) => s.last_day).filter(Boolean).sort().at(-1)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Panel principal"
        description={`Estado de los embalses${lastDay ? ` · último dato ${lastDay}` : ''}. Toca un embalse para ver su proyección a 90 días.`}
      />
      {reservoirs.isPending && <Spinner label="Cargando…" />}
      {reservoirs.data?.length === 0 && (
        <EmptyState title="No tienes embalses asignados">Pide a Gerencia que te asigne los embalses con los que trabajas.</EmptyState>
      )}
      {reservoirs.data && reservoirs.data.length > 0 && (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {reservoirs.data.map((r) => (
            <li key={r.code}>
              <ReservoirCard r={r} s={byCode.get(r.code)} />
            </li>
          ))}
        </ul>
      )}
      <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <MapCard />
        <AlertsPanel />
      </div>
      <ComparisonChart />
      <p className="text-sm text-muted-foreground">
        ¿Dudas con algún término? Consulta la <Link to="/ayuda" className="underline">ayuda y el glosario</Link>.
      </p>
    </div>
  )
}

export function MapPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="Mapa" description="Embalses coloreados según su estado, con capas de lluvia y humedad del suelo sobre sus áreas de influencia." />
      <MapCard height={620} />
    </div>
  )
}
