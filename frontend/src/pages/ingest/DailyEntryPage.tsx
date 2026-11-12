import { FloppyDisk } from '@phosphor-icons/react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import { api, ApiError } from '../../api/client'
import { useReservoirs } from '../../api/reservoirs'
import type { Measurement, QualityIssue } from '../../api/types'
import { HELP } from '../../lib/status'
import { Alert, Button, Card, PageHeader, SelectField, Spinner, TextField } from '../../components/ui'
import { fmt } from '../../lib/format'

interface Saved {
  measurement: Measurement
  warnings: QualityIssue[]
}

const NUMERIC_FIELDS: { key: string; label: string; unit: string; hint?: string; required?: boolean }[] = [
  { key: 'level_m', label: 'Cota', unit: 'm.s.n.m.', hint: HELP.level, required: true },
  { key: 'inflow_m3s', label: 'Caudal de entrada', unit: 'm³/s', hint: 'Aporte de los ríos al embalse.' },
  { key: 'outflow_m3s', label: 'Caudal de salida / extracción', unit: 'm³/s', hint: 'Hacia las plantas potabilizadoras.' },
  { key: 'eco_flow_m3s', label: 'Gasto ecológico', unit: 'm³/s', hint: 'Caudal liberado al río aguas abajo.' },
  { key: 'gate_opening_pct', label: 'Apertura de compuertas', unit: '%', hint: 'Entre 0 y 100.' },
  { key: 'intake_m3s', label: 'Captación', unit: 'm³/s' },
]

function yesterday(): string {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  return d.toLocaleDateString('en-CA') // AAAA-MM-DD en hora local
}

export function DailyEntryPage() {
  const qc = useQueryClient()
  const reservoirs = useReservoirs()
  const [code, setCode] = useState('')
  const [day, setDay] = useState(new Date().toLocaleDateString('en-CA'))
  const [time, setTime] = useState('08:00')
  const [values, setValues] = useState<Record<string, string>>({})
  const [notes, setNotes] = useState('')
  const selected = code || reservoirs.data?.[0]?.code || ''

  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = { day, reading_time: time || null, notes: notes || null }
      for (const { key } of NUMERIC_FIELDS) {
        const v = values[key]?.trim()
        body[key] = v ? Number(v.replace(',', '.')) : null
      }
      return api.post<Saved>(`/reservoirs/${selected}/measurements`, body)
    },
    onSuccess: () => {
      setValues({})
      setNotes('')
      void qc.invalidateQueries({ queryKey: ['status'] })
      void qc.invalidateQueries({ queryKey: ['measurements'] })
    },
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    save.mutate()
  }

  if (reservoirs.isPending) return <Spinner label="Cargando embalses…" />
  const name = reservoirs.data?.find((r) => r.code === selected)?.name ?? selected

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="Registro diario"
        description="Registra la lectura del limnímetro y los caudales del día. El sistema calcula el volumen con la curva vigente y avisa si algo se ve raro."
      />
      {reservoirs.data?.length === 0 && <Alert tone="warning">No tienes embalses asignados. Pide a Gerencia que te asigne uno.</Alert>}

      {save.isSuccess && (
        <Alert tone={save.data.warnings.length ? 'warning' : 'success'} title={`Registro del ${save.data.measurement.day} guardado (${name})`}>
          <p>
            Volumen: {fmt(save.data.measurement.volume_hm3, 1)} hm³ · Disponibilidad: {fmt(save.data.measurement.availability_pct, 1)} % ·
            Reserva: {fmt(save.data.measurement.reserve_days, 0)} días
          </p>
          {save.data.warnings.length > 0 && (
            <ul className="mt-2 list-disc pl-5">
              {save.data.warnings.map((w) => (
                <li key={w.code}>{w.message}</li>
              ))}
            </ul>
          )}
          <Link to={`/embalses/${selected}`} className="mt-2 inline-block font-semibold text-accent underline underline-offset-4">
            Ver el embalse
          </Link>
        </Alert>
      )}
      {save.isError && <Alert tone="error" title="No se guardó el registro">{(save.error as ApiError).message}</Alert>}

      <Card>
        <form onSubmit={onSubmit} className="grid gap-4 sm:grid-cols-2">
          <SelectField label="Embalse" value={selected} onChange={(e) => setCode(e.target.value)} className="sm:col-span-2">
            {reservoirs.data?.map((r) => (
              <option key={r.code} value={r.code}>
                {r.name}
              </option>
            ))}
          </SelectField>
          <div>
            <TextField label="Fecha" type="date" required value={day} max={new Date().toLocaleDateString('en-CA')} onChange={(e) => setDay(e.target.value)} />
            <button type="button" onClick={() => setDay(yesterday())} className="mt-1 min-h-11 cursor-pointer text-sm font-semibold text-accent underline underline-offset-4">
              Usar la fecha de ayer
            </button>
          </div>
          <TextField label="Hora de la lectura" type="time" value={time} onChange={(e) => setTime(e.target.value)} />
          {NUMERIC_FIELDS.map(({ key, label, unit, hint, required }) => (
            <TextField
              key={key}
              label={`${label} (${unit})`}
              inputMode="decimal"
              required={required}
              hint={hint}
              value={values[key] ?? ''}
              onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
            />
          ))}
          <TextField label="Observaciones" className="sm:col-span-2" value={notes} onChange={(e) => setNotes(e.target.value)} />
          <div className="sm:col-span-2">
            <Button type="submit" loading={save.isPending} disabled={!selected || !values.level_m} className="w-full sm:w-auto">
              <FloppyDisk size={20} aria-hidden="true" /> Guardar registro
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}
