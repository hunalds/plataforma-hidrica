import { ArrowsClockwise, CheckCircle, Eye, PaperPlaneTilt, Plus, Trash } from '@phosphor-icons/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import { api, ApiError } from '../../api/client'
import { useReservoirs } from '../../api/reservoirs'
import { MODULES, type AlertItem } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Button, Card, EmptyState, PageHeader, SelectField, Spinner, TextField } from '../../components/ui'
import { fmtDateTime } from '../../lib/format'
import { SeverityBadge } from './severity'

interface Recipient {
  id: number
  name: string
  channel: 'correo' | 'telegram' | 'sms' | 'whatsapp'
  target: string
  reservoir_code: string | null
  min_severity: 'informativa' | 'alerta' | 'critica'
  active: boolean
}

const CHANNEL_LABEL = { correo: 'Correo', telegram: 'Telegram', sms: 'SMS', whatsapp: 'WhatsApp' }
const TARGET_HINT = { correo: 'Correo electrónico', telegram: 'ID del chat de Telegram', sms: 'Teléfono (+58…)', whatsapp: 'Teléfono (+58…)' }

function AlertCard({ a }: { a: AlertItem }) {
  const qc = useQueryClient()
  const ack = useMutation({ mutationFn: () => api.post<AlertItem>(`/alerts/${a.id}/ack`), onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }) })
  return (
    <li className={`rounded-lg border p-4 ${a.resolved_at ? 'border-border opacity-80' : 'border-border bg-surface shadow-sm'}`}>
      <div className="flex flex-wrap items-center gap-2">
        <SeverityBadge severity={a.severity} />
        <Link to={`/embalses/${a.reservoir_code}`} className="font-semibold underline-offset-4 hover:underline">
          {a.reservoir_name}
        </Link>
        <span className="text-sm text-muted-foreground">
          {a.kind === 'proyectada' ? 'Proyectada' : 'Observada'} · {a.direction === 'escasez' ? 'Escasez' : 'Inundación / alivio'}
        </span>
        {a.resolved_at && <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-semibold">Resuelta {fmtDateTime(a.resolved_at)}</span>}
      </div>
      <h3 className="mt-2 font-heading text-lg font-semibold">{a.title}</h3>
      <p className="mt-1">{a.message}</p>
      <p className="mt-2 text-sm text-muted-foreground">
        Creada {fmtDateTime(a.created_at)} · actualizada {fmtDateTime(a.updated_at)}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        {a.acknowledged_by_me ? (
          <span className="inline-flex items-center gap-1 text-sm font-semibold text-status-normal">
            <CheckCircle size={18} weight="fill" aria-hidden="true" /> Ya la viste
          </span>
        ) : (
          <Button variant="secondary" onClick={() => ack.mutate()} loading={ack.isPending}>
            <Eye size={18} aria-hidden="true" /> Marcar como vista
          </Button>
        )}
        {a.acknowledgements.length > 0 && (
          <span className="text-sm text-muted-foreground">Vista por: {a.acknowledgements.map((k) => `${k.user} (${fmtDateTime(k.at)})`).join(', ')}</span>
        )}
      </div>
      {a.deliveries.length > 0 && (
        <details className="mt-2 text-sm">
          <summary className="min-h-11 cursor-pointer py-2 font-semibold">Envíos ({a.deliveries.length})</summary>
          <ul className="space-y-1">
            {a.deliveries.map((d, i) => (
              <li key={i}>
                {CHANNEL_LABEL[d.channel as keyof typeof CHANNEL_LABEL] ?? d.channel} → {d.to}: <b>{d.status}</b> · {fmtDateTime(d.at)}
              </li>
            ))}
          </ul>
        </details>
      )}
    </li>
  )
}

function RecipientsSection() {
  const qc = useQueryClient()
  const reservoirs = useReservoirs()
  const list = useQuery({ queryKey: ['recipients'], queryFn: () => api.get<Recipient[]>('/alerts/recipients') })
  const [form, setForm] = useState<Omit<Recipient, 'id'>>({ name: '', channel: 'correo', target: '', reservoir_code: null, min_severity: 'alerta', active: true })
  const [testResult, setTestResult] = useState<string | null>(null)
  const create = useMutation({
    mutationFn: () => api.post<Recipient>('/alerts/recipients', form),
    onSuccess: () => {
      setForm((f) => ({ ...f, name: '', target: '' }))
      void qc.invalidateQueries({ queryKey: ['recipients'] })
    },
  })
  const remove = useMutation({ mutationFn: (id: number) => api.delete(`/alerts/recipients/${id}`), onSuccess: () => qc.invalidateQueries({ queryKey: ['recipients'] }) })
  const test = useMutation({
    mutationFn: (id: number) => api.post<{ status: string; detail: string | null }>(`/alerts/recipients/${id}/test`),
    onSuccess: (r) => setTestResult(`Prueba: ${r.status}${r.detail ? ` (${r.detail})` : ''}`),
  })
  function onSubmit(e: FormEvent) {
    e.preventDefault()
    create.mutate()
  }
  return (
    <Card>
      <h2 className="text-xl font-semibold">Destinatarios</h2>
      <p className="mt-1 text-muted-foreground">
        Quién recibe las alertas, por qué canal y desde qué severidad. La plataforma siempre muestra todas las alertas.
      </p>
      {testResult && (
        <div className="mt-3">
          <Alert tone="info">{testResult}</Alert>
        </div>
      )}
      {list.data && list.data.length > 0 && (
        <ul className="mt-3 divide-y divide-border">
          {list.data.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span>
                <b>{r.name}</b> · {CHANNEL_LABEL[r.channel]} {r.target} · {r.reservoir_code ?? 'todos los embalses'} · desde {r.min_severity}
                {!r.active && ' · inactivo'}
              </span>
              <span className="flex gap-2">
                <Button variant="secondary" className="min-h-9 text-sm" onClick={() => test.mutate(r.id)}>
                  <PaperPlaneTilt size={16} aria-hidden="true" /> Probar
                </Button>
                <Button variant="secondary" className="min-h-9 text-sm" onClick={() => window.confirm(`¿Eliminar a ${r.name}?`) && remove.mutate(r.id)}>
                  <Trash size={16} aria-hidden="true" /> Eliminar
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={onSubmit} className="mt-4 grid gap-4 border-t border-border pt-4 md:grid-cols-3">
        <TextField label="Nombre o cargo" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <SelectField label="Canal" value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value as Recipient['channel'] })}>
          {Object.entries(CHANNEL_LABEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
              {k === 'sms' || k === 'whatsapp' ? ' (proveedor pendiente)' : ''}
            </option>
          ))}
        </SelectField>
        <TextField label={TARGET_HINT[form.channel]} required value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })} />
        <SelectField label="Embalse" value={form.reservoir_code ?? ''} onChange={(e) => setForm({ ...form, reservoir_code: e.target.value || null })}>
          <option value="">Todos</option>
          {reservoirs.data?.map((r) => (
            <option key={r.code} value={r.code}>
              {r.name}
            </option>
          ))}
        </SelectField>
        <SelectField label="Desde la severidad" value={form.min_severity} onChange={(e) => setForm({ ...form, min_severity: e.target.value as Recipient['min_severity'] })}>
          <option value="informativa">Informativa</option>
          <option value="alerta">Alerta</option>
          <option value="critica">Crítica</option>
        </SelectField>
        <div className="flex items-end">
          <Button type="submit" loading={create.isPending} disabled={!form.name || !form.target}>
            <Plus size={18} aria-hidden="true" /> Agregar
          </Button>
        </div>
        {create.isError && (
          <div className="md:col-span-3">
            <Alert tone="error">{(create.error as ApiError).message}</Alert>
          </div>
        )}
      </form>
    </Card>
  )
}

export function AlertsPage() {
  const { can } = useAuth()
  const qc = useQueryClient()
  const manage = can(MODULES.alerts, 'MANAGE')
  const [filter, setFilter] = useState<'true' | 'false' | ''>('true')
  const q = useQuery({ queryKey: ['alerts', filter], queryFn: () => api.get<AlertItem[]>(`/alerts?limit=200${filter ? `&active=${filter}` : ''}`) })
  const evaluate = useMutation({
    mutationFn: () => api.post<Record<string, { nuevas: number; actualizadas: number; resueltas: number; notificaciones: number }>>('/alerts/evaluate'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Alertas tempranas"
        description="Se generan cuando la cota observada cruza un umbral o cuando la proyección indica que lo cruzará en los próximos 30 días."
        actions={
          manage && (
            <Button onClick={() => evaluate.mutate()} loading={evaluate.isPending}>
              <ArrowsClockwise size={20} aria-hidden="true" /> Evaluar ahora
            </Button>
          )
        }
      />
      {evaluate.isSuccess && (
        <Alert tone="success" title="Evaluación terminada">
          {Object.entries(evaluate.data)
            .map(([k, v]) => `${k}: ${v.nuevas} nuevas, ${v.actualizadas} actualizadas, ${v.resueltas} resueltas`)
            .join(' · ')}
        </Alert>
      )}
      {evaluate.isError && <Alert tone="error">{(evaluate.error as ApiError).message}</Alert>}
      <Card>
        <SelectField label="Mostrar" value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)} className="max-w-xs">
          <option value="true">Activas</option>
          <option value="false">Resueltas</option>
          <option value="">Todas</option>
        </SelectField>
        <div className="mt-4" aria-live="polite">
          {q.isPending && <Spinner label="Cargando alertas…" />}
          {q.data?.length === 0 && <EmptyState title={filter === 'true' ? 'No hay alertas activas' : 'Sin alertas'} />}
          {q.data && q.data.length > 0 && (
            <ul className="space-y-3">
              {q.data.map((a) => (
                <AlertCard key={a.id} a={a} />
              ))}
            </ul>
          )}
        </div>
      </Card>
      {manage && <RecipientsSection />}
    </div>
  )
}
