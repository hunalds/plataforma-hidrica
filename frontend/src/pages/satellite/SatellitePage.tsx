import { CheckCircle, CircleNotch, CloudArrowDown, XCircle } from '@phosphor-icons/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { api, ApiError } from '../../api/client'
import { MODULES, type Coverage, type Job, type SatelliteSource } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Button, Card, PageHeader, SelectField, Spinner, TextField } from '../../components/ui'
import { fmtDateTime } from '../../lib/format'
import { KIND_LABELS, VARIABLE_LABELS } from '../../lib/status'

const NAMES: Record<string, string> = { TULE: 'Tulé', MANUELOTE: 'Manuelote', TRES_RIOS: 'Tres Ríos' }

function JobRow({ j }: { j: Job }) {
  const running = j.status === 'EN_CURSO' || j.status === 'PENDIENTE'
  const icon = running ? (
    <CircleNotch size={20} className="animate-spin text-accent" aria-hidden="true" />
  ) : j.status === 'TERMINADA' ? (
    <CheckCircle size={20} weight="fill" className="text-status-normal" aria-hidden="true" />
  ) : (
    <XCircle size={20} weight="fill" className="text-status-critical" aria-hidden="true" />
  )
  return (
    <li className="py-3">
      <div className="flex flex-wrap items-center gap-2">
        {icon}
        <span className="font-semibold">{KIND_LABELS[j.params.tipo] ?? j.kind}</span>
        <span className="text-sm text-muted-foreground">
          {j.params.desde} → {j.params.hasta} · {j.params.embalses.map((c) => NAMES[c] ?? c).join(', ')}
        </span>
      </div>
      {running && (
        <div className="mt-2">
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={Math.round(j.progress * 100)} aria-valuemin={0} aria-valuemax={100} aria-label="Avance de la descarga">
            <div className="h-full bg-accent transition-[width]" style={{ width: `${j.progress * 100}%` }} />
          </div>
        </div>
      )}
      <p className={`mt-1 text-sm ${j.status === 'FALLIDA' ? 'text-status-critical' : 'text-muted-foreground'}`}>
        {j.status === 'TERMINADA' && j.result ? `${j.result.guardadas} observaciones (${j.result.con_valor} con valor)` : j.message}
        {' · '}
        {fmtDateTime(j.created_at)}
      </p>
    </li>
  )
}

function LaunchForm() {
  const qc = useQueryClient()
  const today = new Date().toLocaleDateString('en-CA')
  const monthAgo = new Date(Date.now() - 30 * 86_400_000).toLocaleDateString('en-CA')
  const [kind, setKind] = useState('precipitacion')
  const [from, setFrom] = useState(monthAgo)
  const [to, setTo] = useState(today)
  const launch = useMutation({
    mutationFn: () => api.post<Job>('/satellite/jobs', { kind, date_from: from, date_to: to }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['satellite-jobs'] }),
  })
  function onSubmit(e: FormEvent) {
    e.preventDefault()
    launch.mutate()
  }
  return (
    <Card>
      <h2 className="text-xl font-semibold">Descargar datos</h2>
      <p className="mt-1 text-muted-foreground">
        La descarga corre en segundo plano: puedes seguir usando la plataforma. NDWI y superficie de agua tardan ~1–2 minutos por mes y
        embalse; para el histórico completo se recomienda la terminal (ver manual técnico).
      </p>
      <form onSubmit={onSubmit} className="mt-4 grid gap-4 sm:grid-cols-4">
        <SelectField label="Dato" value={kind} onChange={(e) => setKind(e.target.value)} className="sm:col-span-2">
          {Object.entries(KIND_LABELS).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </SelectField>
        <TextField label="Desde" type="date" min="2005-01-01" max={today} value={from} onChange={(e) => setFrom(e.target.value)} />
        <TextField label="Hasta" type="date" min="2005-01-01" max={today} value={to} onChange={(e) => setTo(e.target.value)} />
        <div className="flex flex-wrap items-center gap-3 sm:col-span-4">
          <Button type="submit" loading={launch.isPending}>
            <CloudArrowDown size={20} aria-hidden="true" /> Iniciar descarga
          </Button>
          {launch.isError && <Alert tone="error">{(launch.error as ApiError).message}</Alert>}
          {launch.isSuccess && <Alert tone="success">Descarga iniciada. Su avance aparece abajo.</Alert>}
        </div>
      </form>
    </Card>
  )
}

export function SatellitePage() {
  const { can } = useAuth()
  const jobs = useQuery({
    queryKey: ['satellite-jobs'],
    queryFn: () => api.get<Job[]>('/satellite/jobs'),
    // Mientras haya descargas en curso se consulta el avance cada 3 s
    refetchInterval: (query) => (query.state.data?.some((j) => j.status === 'EN_CURSO' || j.status === 'PENDIENTE') ? 3000 : false),
  })
  const coverage = useQuery({ queryKey: ['satellite-coverage', jobs.dataUpdatedAt], queryFn: () => api.get<Coverage[]>('/satellite/coverage') })
  const sources = useQuery({ queryKey: ['satellite-sources'], queryFn: () => api.get<SatelliteSource[]>('/satellite/sources') })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Datos satelitales"
        description="Precipitación, humedad del suelo y espejo de agua de cada embalse, desde fuentes abiertas sin cuenta (sin servicios de Google)."
      />
      {can(MODULES.satellite, 'MANAGE') && <LaunchForm />}

      <Card>
        <h2 className="text-xl font-semibold">Descargas recientes</h2>
        {jobs.isPending && <Spinner label="Cargando…" />}
        {jobs.data?.length === 0 && <p className="mt-2 text-muted-foreground">Todavía no se ha lanzado ninguna descarga.</p>}
        {jobs.data && jobs.data.length > 0 && (
          <ul className="mt-2 divide-y divide-border" aria-live="polite">
            {jobs.data.map((j) => (
              <JobRow key={j.id} j={j} />
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <h2 className="text-xl font-semibold">Datos disponibles</h2>
        {coverage.data?.length === 0 && <p className="mt-2 text-muted-foreground">Sin datos descargados.</p>}
        {coverage.data && coverage.data.length > 0 && (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[680px] text-left text-sm">
              <caption className="sr-only">Cobertura de datos satelitales por embalse</caption>
              <thead className="border-b border-border text-muted-foreground">
                <tr>
                  <th scope="col" className="py-2 pr-3">Embalse</th>
                  <th scope="col" className="py-2 pr-3">Variable</th>
                  <th scope="col" className="py-2 pr-3">Fuente</th>
                  <th scope="col" className="py-2 pr-3">Desde</th>
                  <th scope="col" className="py-2 pr-3">Hasta</th>
                  <th scope="col" className="py-2 pr-3 text-right">Días con valor</th>
                  <th scope="col" className="py-2 text-right">Calidad buena</th>
                </tr>
              </thead>
              <tbody>
                {coverage.data.map((c) => (
                  <tr key={`${c.reservoir_code}${c.variable}${c.source}`} className="border-b border-border last:border-0">
                    <td className="py-2 pr-3 font-semibold">{NAMES[c.reservoir_code] ?? c.reservoir_code}</td>
                    <td className="py-2 pr-3">{VARIABLE_LABELS[c.variable] ?? c.variable}</td>
                    <td className="py-2 pr-3">{c.source}</td>
                    <td className="py-2 pr-3 tabular-nums">{c.first_day}</td>
                    <td className="py-2 pr-3 tabular-nums">{c.last_day}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{c.with_value.toLocaleString('es-VE')}</td>
                    <td className="py-2 text-right tabular-nums">{c.good.toLocaleString('es-VE')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {sources.data && (
        <Card>
          <h2 className="text-xl font-semibold">Fuentes</h2>
          <ul className="mt-2 divide-y divide-border">
            {sources.data.map((s) => (
              <li key={s.clave} className="py-3">
                <p className="font-semibold">{s.nombre}</p>
                <p className="text-sm text-muted-foreground">
                  {s.variables.map((v) => VARIABLE_LABELS[v] ?? v).join(' · ')} — {s.resolucion} — {s.acceso}
                </p>
                <p className="text-xs text-muted-foreground">{s.atribucion}</p>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
