import { Bell, CheckCircle } from '@phosphor-icons/react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'

import { api } from '../../api/client'
import type { AlertItem } from '../../api/types'
import { Card, Spinner } from '../../components/ui'
import { fmtDateTime } from '../../lib/format'
import { SeverityBadge } from './severity'

/** Alertas activas (no cerradas) de los embalses visibles, para el panel principal. */
export function AlertsPanel() {
  const q = useQuery({ queryKey: ['alerts', 'active'], queryFn: () => api.get<AlertItem[]>('/alerts?active=true&limit=8') })
  return (
    <Card>
      <h2 className="flex items-center gap-2 text-xl font-semibold">
        <Bell size={22} aria-hidden="true" /> Alertas activas
      </h2>
      {q.isPending && <Spinner label="Cargando alertas…" />}
      {q.isError && <p className="mt-2 text-muted-foreground">No se pudieron cargar las alertas.</p>}
      {q.data && q.data.length === 0 && (
        <p className="mt-3 flex items-center gap-2 text-status-normal">
          <CheckCircle size={20} weight="fill" aria-hidden="true" /> No hay alertas activas.
        </p>
      )}
      {q.data && q.data.length > 0 && (
        <ul className="mt-3 divide-y divide-border">
          {q.data.map((a) => (
            <li key={a.id} className="py-3">
              <div className="flex flex-wrap items-center gap-2">
                <SeverityBadge severity={a.severity} />
                <span className="font-semibold">{a.reservoir_name}</span>
              </div>
              <p className="mt-1 text-sm">{a.title}</p>
              <p className="text-xs text-muted-foreground">{fmtDateTime(a.created_at)}</p>
            </li>
          ))}
        </ul>
      )}
      <Link to="/alertas" className="mt-3 inline-flex min-h-11 items-center font-semibold text-accent underline underline-offset-4 hover:text-primary">
        Ver todas las alertas
      </Link>
    </Card>
  )
}
