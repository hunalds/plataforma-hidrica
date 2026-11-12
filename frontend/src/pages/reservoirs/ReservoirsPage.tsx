import { CaretRight, MapPinSimpleArea, Warning } from '@phosphor-icons/react'
import { Link } from 'react-router'

import { useReservoirs, useStatuses } from '../../api/reservoirs'
import type { Reservoir, ReservoirStatus } from '../../api/types'
import { AvailabilityBar, LastDataLine, StatusMetrics, TrafficLightBadge } from '../../components/status'
import { Alert, EmptyState, PageHeader, Spinner } from '../../components/ui'

function Chip({ children, tone = 'alert' }: { children: React.ReactNode; tone?: 'alert' | 'muted' }) {
  const cls = tone === 'alert' ? 'bg-status-alert-bg text-status-alert' : 'bg-muted text-muted-foreground'
  return <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-sm font-semibold ${cls}`}>{children}</span>
}

export function ReservoirCard({ r, s }: { r: Reservoir; s: ReservoirStatus | undefined }) {
  return (
    <Link
      to={`/embalses/${r.code}`}
      className="group flex h-full flex-col gap-4 rounded-lg border border-border bg-surface p-5 shadow-sm transition-shadow hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-xl font-semibold">{r.name}</h2>
          {s && <LastDataLine s={s} />}
        </div>
        <CaretRight size={22} aria-hidden="true" className="mt-1 shrink-0 text-muted-foreground group-hover:text-accent" />
      </div>
      {s && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <TrafficLightBadge status={s} />
            {!s.thresholds_defined && <span className="text-xs text-muted-foreground">(umbrales por definir)</span>}
          </div>
          <AvailabilityBar pct={s.availability_pct} />
          <StatusMetrics s={s} compact />
        </>
      )}
      <div className="mt-auto flex flex-wrap gap-2">
        {!r.current_curve && (
          <Chip>
            <Warning size={16} aria-hidden="true" /> Sin curva cota–volumen
          </Chip>
        )}
        {r.current_curve?.notes?.includes('SINTÉTICA') && (
          <Chip>
            <Warning size={16} aria-hidden="true" /> Datos sintéticos
          </Chip>
        )}
        {!r.has_geometry && (
          <Chip tone="muted">
            <MapPinSimpleArea size={16} aria-hidden="true" /> Sin polígono
          </Chip>
        )}
      </div>
    </Link>
  )
}

export function ReservoirsPage() {
  const reservoirs = useReservoirs()
  const statuses = useStatuses()
  const byCode = new Map(statuses.data?.map((s) => [s.reservoir_code, s]))

  return (
    <>
      <PageHeader
        title="Embalses"
        description="Estado actual de cada embalse según el último registro diario. La proyección a 30, 60 y 90 días llega en la Iteración 4."
      />
      {reservoirs.isPending && <Spinner label="Cargando embalses…" />}
      {reservoirs.isError && <Alert tone="error" title="No se pudieron cargar los embalses">{reservoirs.error.message}</Alert>}
      {statuses.isError && <Alert tone="warning">No se pudo calcular el estado operativo: {statuses.error.message}</Alert>}
      {reservoirs.data && reservoirs.data.length === 0 && (
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
    </>
  )
}
