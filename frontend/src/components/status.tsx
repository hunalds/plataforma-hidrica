// Semáforo e indicadores operativos. Siempre color + ícono + texto (accesibilidad: no solo color).
import { CheckCircle, Info, Question, Warning, WarningOctagon } from '@phosphor-icons/react'
import type { ReactNode } from 'react'

import type { Light, ReservoirStatus } from '../api/types'
import { fmt } from '../lib/format'
import { HELP, lightLabel } from '../lib/status'

const LIGHTS: Record<Light, { cls: string; icon: ReactNode }> = {
  verde: { cls: 'bg-status-normal-bg text-status-normal border-status-normal', icon: <CheckCircle size={20} weight="fill" /> },
  amarillo: { cls: 'bg-status-alert-bg text-status-alert border-status-alert', icon: <Warning size={20} weight="fill" /> },
  rojo: { cls: 'bg-status-critical-bg text-status-critical border-status-critical', icon: <WarningOctagon size={20} weight="fill" /> },
  gris: { cls: 'bg-status-unknown-bg text-status-unknown border-status-unknown', icon: <Question size={20} weight="fill" /> },
}

export function TrafficLightBadge({ status, size = 'md' }: { status: Pick<ReservoirStatus, 'light' | 'direction' | 'light_reason'>; size?: 'md' | 'lg' }) {
  const s = LIGHTS[status.light]
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-semibold ${s.cls} ${size === 'lg' ? 'px-3 py-1.5 text-base' : 'px-2 py-0.5 text-sm'}`}
      title={status.light_reason}
    >
      <span aria-hidden="true">{s.icon}</span>
      {lightLabel(status.light, status.direction)}
    </span>
  )
}

/** Indicador con ayuda contextual: el término técnico se explica en lenguaje sencillo. */
export function Metric({ label, value, help, emphasis = false }: { label: string; value: string; help?: string; emphasis?: boolean }) {
  return (
    <div>
      <dt className="flex items-center gap-1 text-sm text-muted-foreground">
        {label}
        {help && (
          <span className="group relative inline-flex">
            <button
              type="button"
              className="inline-flex size-6 cursor-help items-center justify-center rounded-full text-muted-foreground hover:text-accent focus-visible:text-accent"
              aria-label={`Qué significa ${label}`}
            >
              <Info size={16} aria-hidden="true" />
            </button>
            <span
              role="tooltip"
              className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 hidden w-64 -translate-x-1/2 rounded-md bg-foreground p-2 text-sm text-background shadow-lg group-focus-within:block group-hover:block"
            >
              {help}
            </span>
          </span>
        )}
      </dt>
      <dd className={`font-heading font-semibold tabular-nums ${emphasis ? 'text-2xl' : 'text-lg'}`}>{value}</dd>
    </div>
  )
}

export function StatusMetrics({ s, compact = false }: { s: ReservoirStatus; compact?: boolean }) {
  const pct = s.availability_pct
  return (
    <dl className={`grid gap-4 ${compact ? 'grid-cols-2' : 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4'}`}>
      <Metric label="Cota" value={s.level_m !== null ? `${fmt(s.level_m)} m` : '—'} help={HELP.level} emphasis={!compact} />
      <Metric label="Disponibilidad" value={pct !== null ? `${fmt(pct, 1)} %` : '—'} help={HELP.availability} emphasis={!compact} />
      <Metric label="Volumen útil" value={s.useful_volume_hm3 !== null ? `${fmt(s.useful_volume_hm3, 1)} hm³` : '—'} help={HELP.useful} />
      <Metric label="Días de reserva" value={s.reserve_days !== null ? `${fmt(s.reserve_days, 0)} días` : '—'} help={HELP.reserveDays} />
      {!compact && (
        <>
          <Metric label="Volumen total" value={s.volume_hm3 !== null ? `${fmt(s.volume_hm3, 1)} hm³` : '—'} help={HELP.volume} />
          <Metric label="Alivio" value={s.spill_hm3 !== null ? `${fmt(s.spill_hm3, 2)} hm³` : '—'} help={HELP.spill} />
          <Metric
            label="Cambio en 7 días"
            value={s.level_change_7d_m !== null ? `${s.level_change_7d_m > 0 ? '+' : ''}${fmt(s.level_change_7d_m)} m` : '—'}
            help={HELP.change7d}
          />
          <Metric label="Entrada / salida" value={s.inflow_m3s !== null ? `${fmt(s.inflow_m3s, 1)} / ${fmt(s.outflow_m3s, 1)} m³/s` : '—'} />
        </>
      )}
    </dl>
  )
}

/** Barra de disponibilidad con marcas: 0 % (volumen muerto) y 100 % (nivel normal). */
export function AvailabilityBar({ pct }: { pct: number | null }) {
  if (pct === null) return null
  const width = Math.max(0, Math.min(100, pct))
  const color = pct > 100 ? 'bg-status-critical' : pct < 25 ? 'bg-status-alert' : 'bg-accent'
  return (
    <div
      className="h-3 w-full overflow-hidden rounded-full bg-muted"
      role="meter"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label="Disponibilidad"
    >
      <div className={`h-full ${color} transition-[width]`} style={{ width: `${width}%` }} />
    </div>
  )
}

export function LastDataLine({ s }: { s: ReservoirStatus }) {
  if (!s.last_day) return <p className="text-sm text-muted-foreground">Sin mediciones registradas.</p>
  const time = s.last_reading_time ? ` · ${s.last_reading_time.slice(0, 5)}` : ''
  return (
    <p className={`text-sm ${s.is_stale ? 'font-semibold text-status-alert' : 'text-muted-foreground'}`}>
      Último dato: {new Date(`${s.last_day}T00:00`).toLocaleDateString('es-VE', { dateStyle: 'medium' })}
      {time}
      {s.is_stale && ` (hace ${s.days_since_last} días: dato desactualizado)`}
    </p>
  )
}
