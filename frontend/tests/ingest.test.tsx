import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import type { ImportBatch } from '../src/api/types'
import { makeMe, renderApp, tule, tuleStatus } from './helpers'

describe('Estado operativo y semáforo (HU-2.6, HU-2.8)', () => {
  it('la tarjeta del embalse muestra semáforo con texto, disponibilidad y días de reserva', async () => {
    renderApp('/', { 'GET /reservoirs': [tule], 'GET /reservoirs/status': [tuleStatus] }, makeMe('OPERADOR'))
    const card = (await screen.findByRole('heading', { name: 'Tulé' })).closest('a')!
    expect(within(card).getByText('Alerta por escasez')).toBeInTheDocument()
    expect(within(card).getByText('30,7 %')).toBeInTheDocument()
    expect(within(card).getByText('122 días')).toBeInTheDocument()
    expect(within(card).getByRole('meter', { name: 'Disponibilidad' })).toHaveAttribute('aria-valuenow', '31')
  })

  it('avisa cuando el último dato está desactualizado', async () => {
    renderApp(
      '/',
      { 'GET /reservoirs': [tule], 'GET /reservoirs/status': [{ ...tuleStatus, is_stale: true, days_since_last: 12 }] },
      makeMe('OPERADOR'),
    )
    expect(await screen.findByText(/hace 12 días: dato desactualizado/)).toBeInTheDocument()
  })

  it('la ficha explica cada indicador con lenguaje sencillo', async () => {
    renderApp('/embalses/TULE', { 'GET /reservoirs/TULE': tule, 'GET /reservoirs/TULE/curves': [] }, makeMe('GERENCIA'))
    expect(await screen.findByRole('heading', { name: 'Estado actual' })).toBeInTheDocument()
    expect(screen.getByText('Nivel bajo: alerta de escasez')).toBeInTheDocument()
    const help = screen.getByRole('button', { name: 'Qué significa Días de reserva' })
    expect(help.parentElement).toHaveTextContent(/cuántos días alcanzaría el agua útil/)
  })
})

describe('Registro diario manual (HU-2.5)', () => {
  it('el Operador guarda la lectura del día y ve los cálculos y los avisos', async () => {
    const { fetchSpy } = renderApp(
      '/registro',
      {
        'GET /reservoirs': [tule],
        'POST /reservoirs/TULE/measurements': (body) => ({
          status: 201,
          body: {
            measurement: { ...(body as object), volume_hm3: 75.1, availability_pct: 31.2, reserve_days: 124, source: 'MANUAL' },
            warnings: [{ severity: 'aviso', code: 'SUDDEN_JUMP', message: 'Salto brusco: la cota cambió +1,20 m respecto al día anterior.' }],
          },
        }),
      },
      makeMe('OPERADOR'),
    )
    await userEvent.type(await screen.findByLabelText(/^Cota/), '29,45')
    await userEvent.type(screen.getByLabelText(/^Caudal de salida/), '4,1')
    await userEvent.click(screen.getByRole('button', { name: /guardar registro/i }))

    expect(await screen.findByText(/guardado \(Tulé\)/)).toBeInTheDocument()
    expect(screen.getByText(/Disponibilidad: 31,2 %/)).toBeInTheDocument()
    expect(screen.getByText(/Salto brusco/)).toBeInTheDocument()
    const call = fetchSpy.mock.calls.find(([url, init]) => String(url).endsWith('/reservoirs/TULE/measurements') && init?.method === 'POST')
    const sent = JSON.parse(String(call?.[1]?.body))
    expect(sent.level_m).toBe(29.45)
    expect(sent.outflow_m3s).toBe(4.1)
    expect(sent.inflow_m3s).toBeNull()
  })

  it('muestra el motivo si el servidor rechaza el registro', async () => {
    renderApp(
      '/registro',
      {
        'GET /reservoirs': [tule],
        'POST /reservoirs/TULE/measurements': () => ({
          status: 409,
          body: { detail: { code: 'ALREADY_EXISTS', message: 'Ya existe un registro del 2026-11-11. Corrígelo en lugar de crear otro.' } },
        }),
      },
      makeMe('OPERADOR'),
    )
    await userEvent.type(await screen.findByLabelText(/^Cota/), '29')
    await userEvent.click(screen.getByRole('button', { name: /guardar registro/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Ya existe un registro')
  })
})

const preview: ImportBatch = {
  id: 'b1',
  filename: 'importacion_con_errores.xlsx',
  status: 'PREVIEW',
  created_at: '2026-11-12T10:00:00Z',
  confirmed_at: null,
  summary: {
    filas_leidas: 47,
    filas_validas: 37,
    filas_con_error: 10,
    errores: 10,
    avisos: 3,
    por_embalse: { TULE: { desde: '2026-10-16', hasta: '2026-10-31', filas_validas: 10, nuevas: 10, existentes: 0, dias_faltantes: 0 } },
  },
  issues: [
    { severity: 'error', code: 'BAD_DATE', message: "Fecha no válida: '31/02/2026'.", row: 7, reservoir: 'TULE', day: null, field: 'day' },
    { severity: 'aviso', code: 'SUDDEN_JUMP', message: 'Salto brusco: la cota cambió +2,50 m.', row: 26, reservoir: 'MANUELOTE', day: '2026-10-25', field: 'level_m' },
  ],
  issues_total: 2,
  sample: [{ reservoir_code: 'TULE', day: '2026-10-16', level_m: 29.23, volume_hm3: 71.7, volume_source: 'REPORTADO' }],
}

describe('Importación con vista previa (HU-2.4)', () => {
  it('el Ingeniero revisa la vista previa con errores por fila y confirma', async () => {
    renderApp(
      '/importar',
      {
        'GET /ingest/batches': [],
        'POST /ingest/preview': () => ({ status: 201, body: preview }),
        'POST /ingest/batches/b1/confirm': { inserted: 37, updated: 0, skipped: 0 },
      },
      makeMe('INGENIERO'),
    )
    const input = await screen.findByLabelText(/archivo \(\.xlsx o \.csv\)/i)
    await userEvent.upload(input, new File(['x'], 'importacion_con_errores.xlsx'))
    await userEvent.click(screen.getByRole('button', { name: /revisar archivo/i }))

    expect(await screen.findByText(/Revisa la vista previa/)).toBeInTheDocument()
    const table = screen.getByRole('table', { name: 'Errores y avisos por fila' })
    expect(within(table).getByText("Fecha no válida: '31/02/2026'.")).toBeInTheDocument()
    expect(within(table).getAllByRole('row')).toHaveLength(3)

    await userEvent.selectOptions(screen.getByLabelText('Ver'), 'error')
    expect(within(table).getAllByRole('row')).toHaveLength(2)

    await userEvent.click(screen.getByRole('button', { name: /guardar 37 filas/i }))
    expect(await screen.findByText(/37 registros nuevos/)).toBeInTheDocument()
  })

  it('no permite confirmar un archivo sin filas válidas', async () => {
    const empty = { ...preview, summary: { ...preview.summary, filas_validas: 0, por_embalse: {} }, sample: [] }
    renderApp(
      '/importar',
      { 'GET /ingest/batches': [], 'POST /ingest/preview': () => ({ status: 201, body: empty }) },
      makeMe('INGENIERO'),
    )
    await userEvent.upload(await screen.findByLabelText(/archivo \(\.xlsx o \.csv\)/i), new File(['x'], 'malo.csv'))
    await userEvent.click(screen.getByRole('button', { name: /revisar archivo/i }))
    expect(await screen.findByText(/No hay filas válidas para guardar/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /guardar 0 filas/i })).toBeDisabled()
  })
})
