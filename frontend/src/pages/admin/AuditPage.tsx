import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { api } from '../../api/client'
import type { AuditEntry, Page } from '../../api/types'
import { Alert, Button, Card, PageHeader, SelectField, Spinner, TextField } from '../../components/ui'
import { fmtDateTime } from '../../lib/format'

const ACTION_LABELS: Record<string, string> = {
  'login.ok': 'Inicio de sesión',
  'login.fail': 'Intento fallido de inicio de sesión',
  'login.lockout': 'Cuenta bloqueada por intentos fallidos',
  'login.locked': 'Intento con cuenta bloqueada',
  'login.inactive': 'Intento de usuario desactivado',
  logout: 'Cierre de sesión',
  'password.change': 'Cambio de contraseña',
  'password.reset_requested': 'Solicitud de recuperación de contraseña',
  'password.reset': 'Contraseña restablecida por enlace',
  'session.reuse_detected': 'Sesión reutilizada (posible robo): sesiones cerradas',
  'user.create': 'Creación de usuario',
  'user.update': 'Modificación de usuario',
  'user.reset_password': 'Contraseña temporal generada',
  'reservoir.update': 'Modificación de la ficha del embalse',
  'reservoir.geometry': 'Carga de polígono',
  'threshold.update': 'Modificación de umbrales',
  'curve.upload': 'Carga de curva cota–volumen',
}

const PAGE_SIZE = 25

function Values({ value }: { value: Record<string, unknown> | null }) {
  if (!value || Object.keys(value).length === 0) return <span className="text-muted-foreground">—</span>
  return (
    <ul className="space-y-0.5">
      {Object.entries(value).map(([k, v]) => (
        <li key={k} className="break-words">
          <span className="text-muted-foreground">{k}:</span> {Array.isArray(v) ? v.join(', ') || '—' : String(v ?? '—')}
        </li>
      ))}
    </ul>
  )
}

export function AuditPage() {
  const [action, setAction] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [page, setPage] = useState(0)

  const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(page * PAGE_SIZE) })
  if (action) params.set('action', action)
  if (from) params.set('date_from', from)
  if (to) params.set('date_to', to)

  const audit = useQuery({
    queryKey: ['audit', params.toString()],
    queryFn: () => api.get<Page<AuditEntry>>(`/audit?${params}`),
    placeholderData: keepPreviousData,
  })
  const pages = audit.data ? Math.max(1, Math.ceil(audit.data.total / PAGE_SIZE)) : 1

  return (
    <div className="space-y-6">
      <PageHeader title="Bitácora de auditoría" description="Registro de quién hizo qué, cuándo y desde dónde. Solo lectura." />
      <Card>
        <div className="grid gap-4 sm:grid-cols-3">
          <SelectField
            label="Tipo de acción"
            value={action}
            onChange={(e) => {
              setAction(e.target.value)
              setPage(0)
            }}
          >
            <option value="">Todas</option>
            <option value="login">Inicios de sesión</option>
            <option value="password">Contraseñas</option>
            <option value="user.">Usuarios</option>
            <option value="reservoir">Embalses</option>
            <option value="threshold">Umbrales</option>
            <option value="curve">Curvas</option>
          </SelectField>
          <TextField label="Desde" type="date" value={from} onChange={(e) => (setFrom(e.target.value), setPage(0))} />
          <TextField label="Hasta" type="date" value={to} onChange={(e) => (setTo(e.target.value), setPage(0))} />
        </div>
      </Card>

      <Card>
        {audit.isPending && <Spinner label="Cargando bitácora…" />}
        {audit.isError && <Alert tone="error">{audit.error.message}</Alert>}
        {audit.data && (
          <>
            <p className="text-sm text-muted-foreground" aria-live="polite">
              {audit.data.total} registro(s)
            </p>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[860px] text-left text-sm">
                <caption className="sr-only">Registros de auditoría</caption>
                <thead className="border-b border-border text-muted-foreground">
                  <tr>
                    <th scope="col" className="py-2 pr-3">Fecha y hora</th>
                    <th scope="col" className="py-2 pr-3">Usuario</th>
                    <th scope="col" className="py-2 pr-3">Acción</th>
                    <th scope="col" className="py-2 pr-3">Entidad</th>
                    <th scope="col" className="py-2 pr-3">Antes</th>
                    <th scope="col" className="py-2 pr-3">Después</th>
                    <th scope="col" className="py-2">IP</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.data.items.map((e) => (
                    <tr key={e.id} className="border-b border-border align-top last:border-0">
                      <td className="py-2 pr-3 whitespace-nowrap tabular-nums">{fmtDateTime(e.created_at)}</td>
                      <td className="py-2 pr-3">{e.user_email ?? '—'}</td>
                      <td className="py-2 pr-3">{ACTION_LABELS[e.action] ?? e.action}</td>
                      <td className="py-2 pr-3">{e.entity ? `${e.entity} ${e.entity_id ?? ''}` : '—'}</td>
                      <td className="py-2 pr-3"><Values value={e.old_value} /></td>
                      <td className="py-2 pr-3"><Values value={e.new_value} /></td>
                      <td className="py-2 tabular-nums">{e.ip ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-4 flex items-center justify-between gap-3">
              <Button variant="secondary" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
                Anterior
              </Button>
              <span className="text-sm text-muted-foreground">
                Página {page + 1} de {pages}
              </span>
              <Button variant="secondary" disabled={page + 1 >= pages} onClick={() => setPage((p) => p + 1)}>
                Siguiente
              </Button>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
