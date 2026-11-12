import { Copy, Key, UserPlus } from '@phosphor-icons/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { api, ApiError } from '../../api/client'
import { ROLE_LABELS, type Page, type Role, type User } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Button, Card, PageHeader, SelectField, Spinner, TextField } from '../../components/ui'
import { fmtDateTime } from '../../lib/format'
import { useReservoirs } from '../../api/reservoirs'

interface Created {
  user: User
  temporary_password: string
}

function TemporaryPassword({ created, onClose }: { created: Created; onClose: () => void }) {
  const [copied, setCopied] = useState(false)
  return (
    <Alert tone="success" title={`Contraseña temporal de ${created.user.full_name}`}>
      <p className="mt-1">Entrégasela al usuario por un medio seguro. Se muestra una sola vez y deberá cambiarla al entrar.</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <code className="rounded bg-surface px-3 py-2 font-mono text-lg tracking-wide text-foreground">{created.temporary_password}</code>
        <Button
          variant="secondary"
          onClick={() => {
            void navigator.clipboard?.writeText(created.temporary_password).then(() => setCopied(true))
          }}
        >
          <Copy size={18} aria-hidden="true" /> {copied ? 'Copiada' : 'Copiar'}
        </Button>
        <Button variant="secondary" onClick={onClose}>
          Listo
        </Button>
      </div>
    </Alert>
  )
}

function CreateUserForm({ onCreated }: { onCreated: (c: Created) => void }) {
  const qc = useQueryClient()
  const reservoirs = useReservoirs()
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [role, setRole] = useState<Role>('OPERADOR')
  const [codes, setCodes] = useState<string[]>([])
  const create = useMutation({
    mutationFn: () => api.post<Created>('/users', { email, full_name: name, role, reservoir_codes: codes }),
    onSuccess: (c) => {
      setEmail('')
      setName('')
      setCodes([])
      onCreated(c)
      void qc.invalidateQueries({ queryKey: ['users'] })
    },
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    create.mutate()
  }

  return (
    <Card>
      <h2 className="text-xl font-semibold">Nuevo usuario</h2>
      <form onSubmit={onSubmit} className="mt-4 grid gap-4 md:grid-cols-2">
        <TextField label="Nombre completo" required value={name} onChange={(e) => setName(e.target.value)} />
        <TextField label="Correo" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <SelectField label="Rol" value={role} onChange={(e) => setRole(e.target.value as Role)}>
          {(Object.keys(ROLE_LABELS) as Role[]).map((r) => (
            <option key={r} value={r}>
              {ROLE_LABELS[r]}
            </option>
          ))}
        </SelectField>
        <fieldset>
          <legend className="mb-1 font-semibold">Embalses asignados</legend>
          <div className="flex flex-wrap gap-x-4 gap-y-2">
            {reservoirs.data?.map((r) => (
              <label key={r.code} className="inline-flex min-h-11 cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  className="size-5 cursor-pointer"
                  checked={codes.includes(r.code)}
                  onChange={(e) => setCodes((c) => (e.target.checked ? [...c, r.code] : c.filter((x) => x !== r.code)))}
                />
                {r.name}
              </label>
            ))}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">Gerencia ve todos los embalses aunque no se le asignen.</p>
        </fieldset>
        <div className="flex flex-wrap items-center gap-3 md:col-span-2">
          <Button type="submit" loading={create.isPending} disabled={!email || name.trim().length < 3}>
            <UserPlus size={20} aria-hidden="true" /> Crear usuario
          </Button>
          {create.isError && <Alert tone="error">{(create.error as ApiError).message}</Alert>}
        </div>
      </form>
    </Card>
  )
}

export function UsersPage() {
  const qc = useQueryClient()
  const { user: me } = useAuth()
  const [created, setCreated] = useState<Created | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const users = useQuery({ queryKey: ['users'], queryFn: () => api.get<Page<User>>('/users?limit=200') })

  const toggle = useMutation({
    mutationFn: (u: User) => api.patch<User>(`/users/${u.id}`, { is_active: !u.is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
    onError: (e) => setActionError((e as ApiError).message),
  })
  const reset = useMutation({
    mutationFn: (u: User) => api.post<Created>(`/users/${u.id}/reset-password`),
    onSuccess: (c) => setCreated(c),
    onError: (e) => setActionError((e as ApiError).message),
  })

  return (
    <div className="space-y-6">
      <PageHeader title="Usuarios" description="Crea cuentas, asigna roles y embalses, y activa o desactiva el acceso." />
      {created && <TemporaryPassword created={created} onClose={() => setCreated(null)} />}
      {actionError && <Alert tone="error">{actionError}</Alert>}
      <CreateUserForm onCreated={setCreated} />

      <Card>
        <h2 className="text-xl font-semibold">Usuarios registrados {users.data && `(${users.data.total})`}</h2>
        {users.isPending && <Spinner label="Cargando usuarios…" />}
        {users.data && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[720px] text-left">
              <caption className="sr-only">Lista de usuarios</caption>
              <thead className="border-b border-border text-sm text-muted-foreground">
                <tr>
                  <th scope="col" className="py-2 pr-3">Nombre</th>
                  <th scope="col" className="py-2 pr-3">Rol</th>
                  <th scope="col" className="py-2 pr-3">Embalses</th>
                  <th scope="col" className="py-2 pr-3">Último acceso</th>
                  <th scope="col" className="py-2 pr-3">Estado</th>
                  <th scope="col" className="py-2">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {users.data.items.map((u) => (
                  <tr key={u.id} className="border-b border-border last:border-0">
                    <td className="py-3 pr-3">
                      <p className="font-semibold">{u.full_name}</p>
                      <p className="text-sm text-muted-foreground">{u.email}</p>
                    </td>
                    <td className="py-3 pr-3">{ROLE_LABELS[u.role]}</td>
                    <td className="py-3 pr-3 text-sm">{u.role === 'GERENCIA' ? 'Todos' : u.reservoir_codes.join(', ') || '—'}</td>
                    <td className="py-3 pr-3 text-sm tabular-nums">{fmtDateTime(u.last_login_at)}</td>
                    <td className="py-3 pr-3">
                      <span
                        className={`rounded-full px-2 py-1 text-sm font-semibold ${
                          u.is_active ? 'bg-status-normal-bg text-status-normal' : 'bg-status-unknown-bg text-status-unknown'
                        }`}
                      >
                        {u.is_active ? 'Activo' : 'Inactivo'}
                      </span>
                      {u.must_change_password && <p className="mt-1 text-xs text-muted-foreground">Debe cambiar contraseña</p>}
                    </td>
                    <td className="py-3">
                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant="secondary"
                          disabled={u.id === me?.id}
                          onClick={() => {
                            setActionError(null)
                            toggle.mutate(u)
                          }}
                        >
                          {u.is_active ? 'Desactivar' : 'Activar'}
                        </Button>
                        <Button
                          variant="secondary"
                          onClick={() => {
                            setActionError(null)
                            if (window.confirm(`¿Generar una contraseña temporal para ${u.full_name}? Se cerrarán sus sesiones.`)) reset.mutate(u)
                          }}
                        >
                          <Key size={18} aria-hidden="true" /> Restablecer
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
