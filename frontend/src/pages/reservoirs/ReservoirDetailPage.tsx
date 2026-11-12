import { ArrowLeft, DownloadSimple, UploadSimple } from '@phosphor-icons/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'

import { api, API_URL, ApiError } from '../../api/client'
import { MODULES, type CurveSummary, type Reservoir, type Thresholds } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Button, Card, EmptyState, PageHeader, Spinner, TextField } from '../../components/ui'
import { fmt } from '../../lib/format'
import { es } from '../../i18n/es'
import { BalanceSection, RecentMeasurements, StatusCard } from './OperationSections'
import { SatelliteCard } from './SatelliteCard'

const THRESHOLD_FIELDS: { key: keyof Omit<Thresholds, 'updated_at'>; label: string; hint: string }[] = [
  { key: 'low_critical', label: 'Nivel bajo crítico', hint: 'Por debajo: situación crítica de escasez.' },
  { key: 'low_alert', label: 'Nivel bajo de alerta', hint: 'Por debajo: alerta temprana de escasez.' },
  { key: 'high_alert', label: 'Nivel alto de alerta', hint: 'Por encima: vigilancia por posible alivio.' },
  { key: 'spill_level', label: 'Nivel de alivio / inundación', hint: 'Por encima: el embalse alivia o hay riesgo.' },
]

function ThresholdsForm({ reservoir, editable }: { reservoir: Reservoir; editable: boolean }) {
  const qc = useQueryClient()
  const initial = Object.fromEntries(
    THRESHOLD_FIELDS.map(({ key }) => [key, reservoir.thresholds[key]?.toString() ?? '']),
  ) as Record<string, string>
  const [values, setValues] = useState(initial)
  const mutation = useMutation({
    mutationFn: (body: Record<string, number | null>) => api.put<Thresholds>(`/reservoirs/${reservoir.code}/thresholds`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reservoirs'] }),
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    const body = Object.fromEntries(
      THRESHOLD_FIELDS.map(({ key }) => [key, values[key] === '' ? null : Number(values[key].replace(',', '.'))]),
    )
    mutation.mutate(body)
  }

  return (
    <Card>
      <h2 className="text-xl font-semibold">Umbrales de alerta</h2>
      <p className="mt-1 text-muted-foreground">
        Cotas (m.s.n.m.) que activan el semáforo y las alertas. Deben ir en orden: crítico bajo &lt; alerta baja &lt; alerta
        alta &lt; alivio.
      </p>
      <form onSubmit={onSubmit} className="mt-4 grid gap-4 sm:grid-cols-2">
        {THRESHOLD_FIELDS.map(({ key, label, hint }) => (
          <TextField
            key={key}
            label={label}
            hint={hint}
            inputMode="decimal"
            value={values[key]}
            disabled={!editable}
            onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
          />
        ))}
        {editable && (
          <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
            <Button type="submit" loading={mutation.isPending}>
              Guardar umbrales
            </Button>
            <div aria-live="polite" className="min-w-0 flex-1">
              {mutation.isSuccess && <Alert tone="success">Umbrales guardados.</Alert>}
              {mutation.isError && <Alert tone="error">{(mutation.error as ApiError).message}</Alert>}
            </div>
          </div>
        )}
        {!editable && <p className="text-sm text-muted-foreground sm:col-span-2">Solo el Ingeniero puede modificar los umbrales.</p>}
      </form>
    </Card>
  )
}

function CurvesSection({ reservoir, editable }: { reservoir: Reservoir; editable: boolean }) {
  const qc = useQueryClient()
  const curves = useQuery({
    queryKey: ['curves', reservoir.code],
    queryFn: () => api.get<CurveSummary[]>(`/reservoirs/${reservoir.code}/curves`),
  })
  const [file, setFile] = useState<File | null>(null)
  const [validFrom, setValidFrom] = useState(new Date().toISOString().slice(0, 10))
  const [notes, setNotes] = useState('')
  const upload = useMutation({
    mutationFn: () => {
      const form = new FormData()
      form.append('file', file as File)
      form.append('valid_from', validFrom)
      if (notes) form.append('notes', notes)
      return api.post<CurveSummary>(`/reservoirs/${reservoir.code}/curves`, form)
    },
    onSuccess: () => {
      setFile(null)
      setNotes('')
      void qc.invalidateQueries({ queryKey: ['curves', reservoir.code] })
      void qc.invalidateQueries({ queryKey: ['reservoirs'] })
    },
  })

  return (
    <Card>
      <h2 className="text-xl font-semibold">Curva cota–área–volumen</h2>
      <p className="mt-1 text-muted-foreground">{es.glossary.curve} Cada carga crea una nueva versión con su fecha de vigencia.</p>

      {curves.isPending && <Spinner label="Cargando versiones…" />}
      {curves.data && curves.data.length === 0 && (
        <div className="mt-4">
          <EmptyState title="Aún no hay curvas cargadas" />
        </div>
      )}
      {curves.data && curves.data.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[560px] text-left">
            <caption className="sr-only">Versiones de la curva</caption>
            <thead className="border-b border-border text-sm text-muted-foreground">
              <tr>
                <th scope="col" className="py-2 pr-3">Versión</th>
                <th scope="col" className="py-2 pr-3">Vigente desde</th>
                <th scope="col" className="py-2 pr-3">Puntos</th>
                <th scope="col" className="py-2 pr-3">Rango de cotas</th>
                <th scope="col" className="py-2">Nota</th>
              </tr>
            </thead>
            <tbody>
              {curves.data.map((c) => (
                <tr key={c.id} className="border-b border-border last:border-0">
                  <td className="py-2 pr-3 font-semibold">
                    v{c.version}
                    {reservoir.current_curve?.id === c.id && (
                      <span className="ml-2 rounded-full bg-status-normal-bg px-2 py-0.5 text-xs text-status-normal">vigente</span>
                    )}
                  </td>
                  <td className="py-2 pr-3 tabular-nums">{c.valid_from}</td>
                  <td className="py-2 pr-3 tabular-nums">{c.points}</td>
                  <td className="py-2 pr-3 tabular-nums">
                    {fmt(c.min_elevation)} – {fmt(c.max_elevation)} m
                  </td>
                  <td className="py-2 text-sm text-muted-foreground">{c.notes ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editable && (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (file) upload.mutate()
          }}
          className="mt-6 grid gap-4 border-t border-border pt-4 sm:grid-cols-2"
        >
          <div className="sm:col-span-2">
            <a
              href={`${API_URL}/reservoirs/curve-template.csv`}
              download
              className="inline-flex min-h-11 items-center gap-2 font-semibold text-accent underline underline-offset-4 hover:text-primary"
            >
              <DownloadSimple size={20} aria-hidden="true" /> Descargar plantilla CSV
            </a>
          </div>
          <div>
            <label htmlFor="curve-file" className="mb-1 block font-semibold">
              Archivo (.csv o .xlsx) <span className="text-status-critical" aria-hidden="true">*</span>
            </label>
            <input
              id="curve-file"
              type="file"
              accept=".csv,.xlsx"
              required
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block min-h-11 w-full cursor-pointer rounded-md border border-border bg-surface p-2"
            />
          </div>
          <TextField label="Vigente desde" type="date" required value={validFrom} onChange={(e) => setValidFrom(e.target.value)} />
          <TextField label="Nota (opcional)" className="sm:col-span-2" value={notes} onChange={(e) => setNotes(e.target.value)} />
          <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
            <Button type="submit" loading={upload.isPending} disabled={!file}>
              <UploadSimple size={20} aria-hidden="true" /> Cargar nueva versión
            </Button>
            <div aria-live="polite" className="min-w-0 flex-1">
              {upload.isSuccess && <Alert tone="success">Versión {upload.data.version} cargada con {upload.data.points} puntos.</Alert>}
              {upload.isError && <Alert tone="error" title="El archivo tiene errores">{(upload.error as ApiError).message}</Alert>}
            </div>
          </div>
        </form>
      )}
    </Card>
  )
}

export function ReservoirDetailPage() {
  const { code = '' } = useParams()
  const { can } = useAuth()
  const editable = can(MODULES.reservoirs, 'MANAGE')
  const { data: r, isPending, isError, error } = useQuery({
    queryKey: ['reservoirs', code],
    queryFn: () => api.get<Reservoir>(`/reservoirs/${code}`),
  })

  return (
    <>
      <Link to="/" className="mb-4 inline-flex min-h-11 items-center gap-2 font-semibold text-accent hover:text-primary">
        <ArrowLeft size={20} aria-hidden="true" /> Volver a embalses
      </Link>
      {isPending && <Spinner label="Cargando embalse…" />}
      {isError && <Alert tone="error" title="No se pudo cargar el embalse">{error.message}</Alert>}
      {r && (
        <div className="space-y-6">
          <PageHeader title={`Embalse ${r.name}`} description={r.description ?? undefined} />
          <StatusCard code={r.code} />
          <SatelliteCard code={r.code} />
          <RecentMeasurements code={r.code} />
          <BalanceSection code={r.code} />
          <Card>
            <h2 className="text-xl font-semibold">Ficha técnica</h2>
            <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[
                ['Cuenca', r.basin ?? 'Por definir'],
                ['Registros desde', r.records_start ?? '—'],
                ['Cota normal', `${fmt(r.normal_level)} m.s.n.m.`],
                ['Cota de volumen muerto', `${fmt(r.dead_level)} m.s.n.m.`],
                ['Volumen al nivel normal', r.normal_volume_hm3 !== null ? `${fmt(r.normal_volume_hm3, 1)} hm³` : '—'],
                ['Volumen muerto', r.dead_volume_hm3 !== null ? `${fmt(r.dead_volume_hm3, 1)} hm³` : '—'],
                ['Capacidad útil', r.useful_capacity_hm3 !== null ? `${fmt(r.useful_capacity_hm3, 1)} hm³` : '—'],
                ['Polígono del embalse', r.has_geometry ? 'Cargado' : 'Pendiente'],
                ['Polígono de la cuenca', r.has_basin_geometry ? 'Cargado' : 'Pendiente'],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt className="text-sm text-muted-foreground">{label}</dt>
                  <dd className="font-semibold tabular-nums">{value}</dd>
                </div>
              ))}
            </dl>
            {r.current_curve && (
              <p className="mt-4 text-sm text-muted-foreground">
                Volúmenes calculados con la curva v{r.current_curve.version} (vigente desde {r.current_curve.valid_from}).
              </p>
            )}
          </Card>
          <ThresholdsForm key={JSON.stringify(r.thresholds)} reservoir={r} editable={editable} />
          <CurvesSection reservoir={r} editable={editable} />
        </div>
      )}
    </>
  )
}
