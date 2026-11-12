import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import type { Job } from '../src/api/types'
import { makeMe, renderApp, tule } from './helpers'

const job = (over: Partial<Job> = {}): Job => ({
  id: 'j1',
  kind: 'satelite.precipitacion',
  params: { tipo: 'precipitacion', embalses: ['TULE', 'MANUELOTE'], desde: '2026-10-01', hasta: '2026-10-31' },
  status: 'EN_CURSO',
  progress: 0.4,
  message: 'Precipitación (CHIRPS): 2026-10-01 a 2026-10-31',
  result: null,
  created_at: '2026-11-12T10:00:00Z',
  started_at: '2026-11-12T10:00:01Z',
  finished_at: null,
  ...over,
})

describe('Indicadores satelitales en la ficha (HU-3.7)', () => {
  it('muestra lluvia, anomalía, humedad y espejo de agua con el aviso de geometría provisional', async () => {
    renderApp('/embalses/TULE', { 'GET /reservoirs/TULE': tule, 'GET /reservoirs/TULE/curves': [] }, makeMe('OPERADOR'))
    const card = (await screen.findByRole('heading', { name: 'Indicadores satelitales' })).closest('section')!
    expect(within(card).getByText('42 mm')).toBeInTheDocument()
    expect(within(card).getByText('-14 %')).toBeInTheDocument()
    expect(within(card).getByText('23,7 km²')).toBeInTheDocument()
    expect(within(card).getByText('72 %')).toBeInTheDocument() // 23,7 de 32,8 km²
    expect(within(card).getByText(/Geometrías provisionales/)).toBeInTheDocument()
  })
})

describe('Pantalla de datos satelitales (HU-3.7)', () => {
  const base = { 'GET /satellite/coverage': [], 'GET /satellite/sources': [], 'GET /reservoirs': [tule] }

  it('el Ingeniero lanza una descarga y ve su avance', async () => {
    let jobs: Job[] = []
    const { fetchSpy } = renderApp(
      '/satelite',
      {
        ...base,
        'GET /satellite/jobs': () => ({ body: jobs }),
        'POST /satellite/jobs': (body) => {
          jobs = [job()]
          return { status: 202, body: { ...job(), params: { ...job().params, tipo: (body as { kind: string }).kind } } }
        },
      },
      makeMe('INGENIERO'),
    )
    await userEvent.selectOptions(await screen.findByLabelText('Dato'), 'humedad_suelo')
    await userEvent.click(screen.getByRole('button', { name: /iniciar descarga/i }))
    expect(await screen.findByText(/Descarga iniciada/)).toBeInTheDocument()
    expect(await screen.findByRole('progressbar', { name: 'Avance de la descarga' })).toHaveAttribute('aria-valuenow', '40')
    const call = fetchSpy.mock.calls.find(([u, i]) => String(u).endsWith('/satellite/jobs') && i?.method === 'POST')
    expect(JSON.parse(String(call?.[1]?.body)).kind).toBe('humedad_suelo')
  })

  it('Gerencia consulta pero no ve el formulario de descarga', async () => {
    renderApp(
      '/satelite',
      { ...base, 'GET /satellite/jobs': [job({ status: 'TERMINADA', progress: 1, result: { guardadas: 62, con_valor: 62 } })] },
      makeMe('GERENCIA'),
    )
    expect(await screen.findByText(/62 observaciones/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /iniciar descarga/i })).not.toBeInTheDocument()
  })

  it('el Operador no tiene acceso al módulo', async () => {
    renderApp('/satelite', { ...base, 'GET /satellite/jobs': [] }, makeMe('OPERADOR'))
    expect(await screen.findByRole('heading', { name: 'Panel principal' })).toBeInTheDocument()
  })
})
