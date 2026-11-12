import { CaretRight, MapPinSimpleArea, Warning } from '@phosphor-icons/react'
import { Link } from 'react-router'

import { useReservoirs } from '../../api/reservoirs'
import { Alert, EmptyState, PageHeader, Spinner } from '../../components/ui'
import { fmt } from '../../lib/format'
import { es } from '../../i18n/es'

function Stat({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <div title={title}>
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="font-heading text-lg font-semibold tabular-nums">{value}</dd>
    </div>
  )
}

export function ReservoirsPage() {
  const { data, isPending, isError, error } = useReservoirs()

  return (
    <>
      <PageHeader
        title="Embalses"
        description="Datos de referencia de cada embalse. El nivel actual, la proyección y el semáforo se incorporan en las próximas iteraciones."
      />
      {isPending && <Spinner label="Cargando embalses…" />}
      {isError && <Alert tone="error" title="No se pudieron cargar los embalses">{error.message}</Alert>}
      {data && data.length === 0 && (
        <EmptyState title="No tienes embalses asignados">Pide a Gerencia que te asigne los embalses con los que trabajas.</EmptyState>
      )}
      {data && data.length > 0 && (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {data.map((r) => (
            <li key={r.code}>
              <Link
                to={`/embalses/${r.code}`}
                className="group block h-full rounded-lg border border-border bg-surface p-5 shadow-sm transition-shadow hover:shadow-md"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h2 className="text-xl font-semibold">{r.name}</h2>
                    <p className="text-sm text-muted-foreground">{r.basin ?? 'Cuenca por definir'}</p>
                  </div>
                  <CaretRight size={22} aria-hidden="true" className="mt-1 text-muted-foreground group-hover:text-accent" />
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-3">
                  <Stat label="Cota normal" value={`${fmt(r.normal_level)} m`} title={es.glossary.normal} />
                  <Stat label="Cota vol. muerto" value={`${fmt(r.dead_level)} m`} title={es.glossary.dead} />
                  <Stat
                    label="Capacidad útil"
                    value={r.useful_capacity_hm3 !== null ? `${fmt(r.useful_capacity_hm3, 1)} hm³` : '—'}
                    title={es.glossary.useful}
                  />
                  <Stat label="Registros desde" value={r.records_start ? r.records_start.slice(0, 4) : '—'} />
                </dl>
                <div className="mt-4 flex flex-wrap gap-2 text-sm">
                  {!r.current_curve && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-status-alert-bg px-2 py-1 font-semibold text-status-alert">
                      <Warning size={16} aria-hidden="true" /> Sin curva cota–volumen
                    </span>
                  )}
                  {r.current_curve?.notes?.includes('SINTÉTICA') && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-status-alert-bg px-2 py-1 font-semibold text-status-alert">
                      <Warning size={16} aria-hidden="true" /> Curva sintética
                    </span>
                  )}
                  {!r.has_geometry && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-1 text-muted-foreground">
                      <MapPinSimpleArea size={16} aria-hidden="true" /> Sin polígono
                    </span>
                  )}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
