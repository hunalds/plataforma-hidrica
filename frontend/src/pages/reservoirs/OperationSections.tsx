import { Warning } from '@phosphor-icons/react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'

import { api } from '../../api/client'
import { MODULES, type Balance, type Measurement, type ReservoirStatus } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { AvailabilityBar, LastDataLine, StatusMetrics, TrafficLightBadge } from '../../components/status'
import { Alert, Card, EmptyState, SelectField, Spinner } from '../../components/ui'
import { fmt } from '../../lib/format'

const FLAG_LABELS: Record<string, string> = {
  SUDDEN_JUMP: 'Salto brusco',
  BELOW_DEAD: 'Bajo volumen muerto',
  FAR_ABOVE_NORMAL: 'Muy sobre el normal',
  VOLUME_MISMATCH: 'Volumen ≠ curva',
  NO_CURVE: 'Sin curva',
}

export function StatusCard({ code }: { code: string }) {
  const { can } = useAuth()
  const status = useQuery({ queryKey: ['status', code], queryFn: () => api.get<ReservoirStatus>(`/reservoirs/${code}/status`) })
  if (status.isPending) return <Spinner label="Calculando estado actual…" />
  if (status.isError) return <Alert tone="error">{status.error.message}</Alert>
  const s = status.data
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Estado actual</h2>
          <LastDataLine s={s} />
        </div>
        <TrafficLightBadge status={s} size="lg" />
      </div>
      <p className="mt-2 text-muted-foreground">
        {s.light_reason}
        {!s.thresholds_defined && ' · Los umbrales aún no están definidos: se usan la cota normal y la de volumen muerto.'}
      </p>
      {s.missing_curve && s.level_m !== null && (
        <div className="mt-3">
          <Alert tone="warning">No hay curva cota–volumen vigente: no se pueden calcular volúmenes ni días de reserva.</Alert>
        </div>
      )}
      {s.level_m === null && can(MODULES.ingest, 'MANAGE') && (
        <p className="mt-3">
          <Link to="/registro" className="font-semibold text-accent underline underline-offset-4 hover:text-primary">
            Registrar el movimiento del día
          </Link>
        </p>
      )}
      {s.level_m !== null && (
        <div className="mt-4 space-y-4">
          <AvailabilityBar pct={s.availability_pct} />
          <StatusMetrics s={s} />
        </div>
      )}
    </Card>
  )
}

export function RecentMeasurements({ code }: { code: string }) {
  const [days, setDays] = useState(30)
  const q = useQuery({
    queryKey: ['measurements', code, days],
    queryFn: () => api.get<Measurement[]>(`/reservoirs/${code}/measurements?limit=${days}`),
    placeholderData: keepPreviousData,
  })
  return (
    <Card>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Movimiento diario</h2>
          <p className="text-muted-foreground">Registros del limnímetro y caudales, con los cálculos de cada día.</p>
        </div>
        <SelectField label="Mostrar" value={String(days)} onChange={(e) => setDays(Number(e.target.value))} className="w-40">
          <option value="7">7 días</option>
          <option value="30">30 días</option>
          <option value="90">90 días</option>
          <option value="365">1 año</option>
        </SelectField>
      </div>
      {q.isPending && <Spinner label="Cargando registros…" />}
      {q.data && q.data.length === 0 && (
        <div className="mt-4">
          <EmptyState title="Sin registros todavía">Importa el histórico o registra el movimiento del día.</EmptyState>
        </div>
      )}
      {q.data && q.data.length > 0 && (
        <div className="mt-4 max-h-[28rem] overflow-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <caption className="sr-only">Movimiento diario del embalse</caption>
            <thead className="sticky top-0 border-b border-border bg-surface text-muted-foreground">
              <tr>
                <th scope="col" className="py-2 pr-3">Fecha</th>
                <th scope="col" className="py-2 pr-3 text-right">Cota (m)</th>
                <th scope="col" className="py-2 pr-3 text-right">Volumen (hm³)</th>
                <th scope="col" className="py-2 pr-3 text-right">Disp. (%)</th>
                <th scope="col" className="py-2 pr-3 text-right">Reserva (días)</th>
                <th scope="col" className="py-2 pr-3 text-right">Entrada (m³/s)</th>
                <th scope="col" className="py-2 pr-3 text-right">Salida (m³/s)</th>
                <th scope="col" className="py-2 pr-3 text-right">Ecológico (m³/s)</th>
                <th scope="col" className="py-2">Calidad</th>
              </tr>
            </thead>
            <tbody>
              {q.data.map((m) => (
                <tr key={m.day} className="border-b border-border last:border-0">
                  <td className="py-1.5 pr-3 whitespace-nowrap tabular-nums">{m.day}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{fmt(m.level_m)}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{fmt(m.volume_hm3, 1)}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{fmt(m.availability_pct, 1)}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{fmt(m.reserve_days, 0)}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{fmt(m.inflow_m3s)}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{fmt(m.outflow_m3s)}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{fmt(m.eco_flow_m3s)}</td>
                  <td className="py-1.5">
                    {m.quality_flags?.map((f) => (
                      <span key={f} className="mr-1 inline-flex items-center gap-1 rounded bg-status-alert-bg px-1.5 py-0.5 text-xs font-semibold text-status-alert">
                        <Warning size={12} aria-hidden="true" />
                        {FLAG_LABELS[f] ?? f}
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

export function BalanceSection({ code }: { code: string }) {
  const q = useQuery({ queryKey: ['balance', code], queryFn: () => api.get<Balance>(`/reservoirs/${code}/balance`) })
  if (q.isPending) return <Spinner label="Calculando balance…" />
  if (q.isError || !q.data || q.data.days.length === 0) return null
  const t = q.data.totals
  const rows: [string, number | null | undefined, string][] = [
    ['Entradas', t.inflow_hm3, 'Aporte de los ríos'],
    ['Salidas (extracción)', t.outflow_hm3 !== null && t.outflow_hm3 !== undefined ? -t.outflow_hm3 : null, 'Hacia las plantas potabilizadoras'],
    ['Gasto ecológico', t.eco_hm3 !== null && t.eco_hm3 !== undefined ? -t.eco_hm3 : null, 'Liberado al río'],
    ['Alivio estimado', t.spill_estimate_hm3 !== null && t.spill_estimate_hm3 !== undefined ? -t.spill_estimate_hm3 : null, 'Vertido por el aliviadero'],
    ['Cambio de volumen observado', t.observed_change_hm3, 'Según la cota medida'],
    ['Diferencia no explicada', t.residual_hm3, 'Evaporación, filtraciones y errores de medición'],
  ]
  return (
    <Card>
      <h2 className="text-xl font-semibold">Balance hídrico</h2>
      <p className="text-muted-foreground">
        Del {q.data.date_from} al {q.data.date_to} ({q.data.days.length} días), en hm³.
      </p>
      <dl className="mt-4 divide-y divide-border">
        {rows.map(([label, value, help]) => (
          <div key={label} className="flex flex-wrap items-baseline justify-between gap-2 py-2">
            <dt>
              <span className="font-semibold">{label}</span>
              <span className="ml-2 text-sm text-muted-foreground">{help}</span>
            </dt>
            <dd className="font-heading font-semibold tabular-nums">
              {value === null || value === undefined ? '—' : `${value > 0 ? '+' : ''}${fmt(value, 2)}`}
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-sm text-muted-foreground">{q.data.note}</p>
    </Card>
  )
}
