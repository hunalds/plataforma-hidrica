import { CheckCircle, DownloadSimple, FileArrowUp, Trash, WarningCircle, XCircle } from '@phosphor-icons/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { api, API_URL, ApiError } from '../../api/client'
import type { ImportBatch, QualityIssue } from '../../api/types'
import { Alert, Button, Card, PageHeader, SelectField } from '../../components/ui'
import { fmt, fmtDateTime } from '../../lib/format'

const RESERVOIR_NAMES: Record<string, string> = { TULE: 'Tulé', MANUELOTE: 'Manuelote', TRES_RIOS: 'Tres Ríos' }

function SummaryCards({ b }: { b: ImportBatch }) {
  const s = b.summary
  const items: [string, number, string][] = [
    ['Filas leídas', s.filas_leidas, 'text-foreground'],
    ['Filas válidas', s.filas_validas, 'text-status-normal'],
    ['Filas con error', s.filas_con_error, s.filas_con_error ? 'text-status-critical' : 'text-foreground'],
    ['Avisos', s.avisos, s.avisos ? 'text-status-alert' : 'text-foreground'],
  ]
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {items.map(([label, value, cls]) => (
        <div key={label} className="rounded-lg border border-border p-3">
          <dt className="text-sm text-muted-foreground">{label}</dt>
          <dd className={`font-heading text-2xl font-semibold tabular-nums ${cls}`}>{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function IssuesTable({ issues, total }: { issues: QualityIssue[]; total: number }) {
  const [filter, setFilter] = useState<'todos' | 'error' | 'aviso'>('todos')
  const shown = issues.filter((i) => filter === 'todos' || i.severity === filter)
  if (issues.length === 0) return <Alert tone="success">El archivo no tiene errores ni avisos.</Alert>
  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h3 className="text-lg font-semibold">Problemas encontrados</h3>
        <SelectField label="Ver" value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)} className="w-44">
          <option value="todos">Todos</option>
          <option value="error">Solo errores</option>
          <option value="aviso">Solo avisos</option>
        </SelectField>
      </div>
      {total > issues.length && <p className="text-sm text-muted-foreground">Se muestran los primeros {issues.length} de {total}.</p>}
      <div className="mt-2 max-h-96 overflow-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <caption className="sr-only">Errores y avisos por fila</caption>
          <thead className="sticky top-0 border-b border-border bg-surface text-muted-foreground">
            <tr>
              <th scope="col" className="py-2 pr-3">Tipo</th>
              <th scope="col" className="py-2 pr-3">Fila</th>
              <th scope="col" className="py-2 pr-3">Embalse</th>
              <th scope="col" className="py-2 pr-3">Fecha</th>
              <th scope="col" className="py-2">Detalle</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((i, n) => (
              <tr key={n} className="border-b border-border align-top last:border-0">
                <td className="py-1.5 pr-3">
                  {i.severity === 'error' ? (
                    <span className="inline-flex items-center gap-1 font-semibold text-status-critical">
                      <XCircle size={16} weight="fill" aria-hidden="true" /> Error
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 font-semibold text-status-alert">
                      <WarningCircle size={16} weight="fill" aria-hidden="true" /> Aviso
                    </span>
                  )}
                </td>
                <td className="py-1.5 pr-3 tabular-nums">{i.row ?? '—'}</td>
                <td className="py-1.5 pr-3">{i.reservoir ? (RESERVOIR_NAMES[i.reservoir] ?? i.reservoir) : '—'}</td>
                <td className="py-1.5 pr-3 tabular-nums whitespace-nowrap">{i.day ?? '—'}</td>
                <td className="py-1.5">{i.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function ImportPage() {
  const qc = useQueryClient()
  const [file, setFile] = useState<File | null>(null)
  const [batch, setBatch] = useState<ImportBatch | null>(null)
  const [overwrite, setOverwrite] = useState(false)
  const history = useQuery({ queryKey: ['batches'], queryFn: () => api.get<ImportBatch[]>('/ingest/batches') })

  const upload = useMutation({
    mutationFn: () => {
      const form = new FormData()
      form.append('file', file as File)
      return api.post<ImportBatch>('/ingest/preview', form)
    },
    onSuccess: (b) => {
      setBatch(b)
      setOverwrite(false)
      void qc.invalidateQueries({ queryKey: ['batches'] })
    },
  })
  const confirm = useMutation({
    mutationFn: () => api.post<{ inserted: number; updated: number; skipped: number }>(`/ingest/batches/${batch!.id}/confirm`, { overwrite }),
    onSuccess: () => {
      setBatch(null)
      setFile(null)
      for (const key of ['batches', 'status', 'measurements', 'balance']) void qc.invalidateQueries({ queryKey: [key] })
    },
  })
  const discard = useMutation({
    mutationFn: () => api.post(`/ingest/batches/${batch!.id}/discard`),
    onSuccess: () => {
      setBatch(null)
      void qc.invalidateQueries({ queryKey: ['batches'] })
    },
  })

  const existing = batch ? Object.values(batch.summary.por_embalse).reduce((a, r) => a + r.existentes, 0) : 0

  return (
    <div className="space-y-6">
      <PageHeader
        title="Importar datos"
        description="Carga el movimiento diario desde Excel o CSV. Primero verás una vista previa con los problemas encontrados; nada se guarda hasta que confirmes."
      />

      {confirm.isSuccess && (
        <Alert tone="success" title="Importación guardada">
          {confirm.data.inserted} registros nuevos, {confirm.data.updated} actualizados y {confirm.data.skipped} omitidos (ya existían).
        </Alert>
      )}

      <Card>
        <h2 className="text-xl font-semibold">1. Elige el archivo</h2>
        <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1">
          <a href={`${API_URL}/ingest/template.xlsx`} download className="inline-flex min-h-11 items-center gap-2 font-semibold text-accent underline underline-offset-4 hover:text-primary">
            <DownloadSimple size={20} aria-hidden="true" /> Plantilla Excel
          </a>
          <a href={`${API_URL}/ingest/template.csv`} download className="inline-flex min-h-11 items-center gap-2 font-semibold text-accent underline underline-offset-4 hover:text-primary">
            <DownloadSimple size={20} aria-hidden="true" /> Plantilla CSV
          </a>
        </div>
        <form
          className="mt-4 flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault()
            if (file) upload.mutate()
          }}
        >
          <div className="min-w-0 flex-1">
            <label htmlFor="import-file" className="mb-1 block font-semibold">
              Archivo (.xlsx o .csv)
            </label>
            <input
              id="import-file"
              type="file"
              accept=".xlsx,.csv"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null)
                setBatch(null)
              }}
              className="block min-h-11 w-full cursor-pointer rounded-md border border-border bg-surface p-2"
            />
          </div>
          <Button type="submit" loading={upload.isPending} disabled={!file}>
            <FileArrowUp size={20} aria-hidden="true" /> Revisar archivo
          </Button>
        </form>
        {upload.isError && (
          <div className="mt-3">
            <Alert tone="error">{(upload.error as ApiError).message}</Alert>
          </div>
        )}
      </Card>

      {batch && (
        <Card>
          <h2 className="text-xl font-semibold">2. Revisa la vista previa · {batch.filename}</h2>
          <div className="mt-4 space-y-6">
            <SummaryCards b={batch} />
            {Object.keys(batch.summary.por_embalse).length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] text-left text-sm">
                  <caption className="sr-only">Resumen por embalse</caption>
                  <thead className="border-b border-border text-muted-foreground">
                    <tr>
                      <th scope="col" className="py-2 pr-3">Embalse</th>
                      <th scope="col" className="py-2 pr-3">Período</th>
                      <th scope="col" className="py-2 pr-3 text-right">Válidas</th>
                      <th scope="col" className="py-2 pr-3 text-right">Nuevas</th>
                      <th scope="col" className="py-2 pr-3 text-right">Ya existían</th>
                      <th scope="col" className="py-2 text-right">Días faltantes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(batch.summary.por_embalse).map(([code, r]) => (
                      <tr key={code} className="border-b border-border last:border-0">
                        <td className="py-2 pr-3 font-semibold">{RESERVOIR_NAMES[code] ?? code}</td>
                        <td className="py-2 pr-3 tabular-nums">{r.desde} → {r.hasta}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{r.filas_validas}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{r.nuevas}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{r.existentes}</td>
                        <td className="py-2 text-right tabular-nums">{r.dias_faltantes}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <IssuesTable issues={batch.issues} total={batch.issues_total} />
            {batch.sample.length > 0 && (
              <details>
                <summary className="min-h-11 cursor-pointer py-2 font-semibold">Ver las primeras {batch.sample.length} filas válidas</summary>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[560px] text-left text-sm">
                    <thead className="border-b border-border text-muted-foreground">
                      <tr>
                        <th scope="col" className="py-2 pr-3">Embalse</th>
                        <th scope="col" className="py-2 pr-3">Fecha</th>
                        <th scope="col" className="py-2 pr-3 text-right">Cota</th>
                        <th scope="col" className="py-2 pr-3 text-right">Volumen</th>
                        <th scope="col" className="py-2">Origen del volumen</th>
                      </tr>
                    </thead>
                    <tbody>
                      {batch.sample.map((r) => (
                        <tr key={`${r.reservoir_code}${r.day}`} className="border-b border-border last:border-0">
                          <td className="py-1.5 pr-3">{RESERVOIR_NAMES[r.reservoir_code] ?? r.reservoir_code}</td>
                          <td className="py-1.5 pr-3 tabular-nums">{r.day}</td>
                          <td className="py-1.5 pr-3 text-right tabular-nums">{fmt(r.level_m ?? null)}</td>
                          <td className="py-1.5 pr-3 text-right tabular-nums">{fmt(r.volume_hm3 ?? null, 2)}</td>
                          <td className="py-1.5">{r.volume_source === 'CURVA' ? 'Calculado con la curva' : r.volume_source === 'REPORTADO' ? 'Del archivo' : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}

            <div className="border-t border-border pt-4">
              <h2 className="text-xl font-semibold">3. Confirma</h2>
              {batch.summary.filas_validas === 0 ? (
                <Alert tone="error">No hay filas válidas para guardar. Corrige el archivo y vuelve a cargarlo.</Alert>
              ) : (
                <>
                  <p className="mt-1 text-muted-foreground">
                    Se guardarán {batch.summary.filas_validas} filas válidas. Las filas con error no se guardan.
                  </p>
                  {existing > 0 && (
                    <label className="mt-3 flex min-h-11 cursor-pointer items-center gap-3">
                      <input type="checkbox" className="size-5 cursor-pointer" checked={overwrite} onChange={(e) => setOverwrite(e.target.checked)} />
                      Reemplazar los {existing} días que ya existen en la base
                    </label>
                  )}
                </>
              )}
              <div className="mt-3 flex flex-wrap gap-3">
                <Button onClick={() => confirm.mutate()} loading={confirm.isPending} disabled={batch.summary.filas_validas === 0}>
                  <CheckCircle size={20} aria-hidden="true" /> Guardar {batch.summary.filas_validas} filas
                </Button>
                <Button variant="secondary" onClick={() => discard.mutate()} loading={discard.isPending}>
                  <Trash size={20} aria-hidden="true" /> Descartar
                </Button>
              </div>
              {confirm.isError && (
                <div className="mt-3">
                  <Alert tone="error">{(confirm.error as ApiError).message}</Alert>
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      <Card>
        <h2 className="text-xl font-semibold">Importaciones recientes</h2>
        {history.data && history.data.length === 0 && <p className="mt-2 text-muted-foreground">Aún no hay importaciones.</p>}
        {history.data && history.data.length > 0 && (
          <ul className="mt-2 divide-y divide-border">
            {history.data.map((b) => (
              <li key={b.id} className="flex flex-wrap justify-between gap-2 py-2 text-sm">
                <span className="font-semibold">{b.filename}</span>
                <span className="text-muted-foreground">
                  {fmtDateTime(b.created_at)} · {b.summary.filas_validas} válidas · {b.summary.errores} errores ·{' '}
                  {{ PREVIEW: 'Vista previa', CONFIRMED: 'Guardada', DISCARDED: 'Descartada' }[b.status]}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
