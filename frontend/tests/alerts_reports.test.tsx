import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { AlertItem } from '../src/api/types'
import { makeMe, renderApp, tule } from './helpers'

const alert: AlertItem = {
  id: 5,
  reservoir_code: 'TULE',
  reservoir_name: 'Tulé',
  kind: 'observada',
  direction: 'escasez',
  severity: 'alerta',
  threshold: 'low_alert',
  threshold_level: 29,
  title: 'Nivel bajo de alerta alcanzado',
  message: 'La cota del 11/11/2026 es 28,50 m.',
  value: 28.5,
  horizon_days: null,
  probability: null,
  event_day: '2026-11-11',
  created_at: '2026-11-12T08:00:00Z',
  updated_at: '2026-11-12T08:00:00Z',
  resolved_at: null,
  acknowledged_by_me: false,
  acknowledgements: [],
  deliveries: [{ channel: 'correo', status: 'enviada', to: 'Director <d@x.com>', at: '2026-11-12T08:00:01Z' }],
}

describe('Alertas (M9)', () => {
  it('el Operador ve la alerta, sus envíos y la marca como vista', async () => {
    let acked = false
    renderApp(
      '/alertas',
      {
        'GET /reservoirs': [tule],
        'GET /alerts': () => ({ body: [{ ...alert, acknowledged_by_me: acked }] }),
        'POST /alerts/5/ack': () => {
          acked = true
          return { body: { ...alert, acknowledged_by_me: true } }
        },
      },
      makeMe('OPERADOR'),
    )
    expect(await screen.findByRole('heading', { name: 'Nivel bajo de alerta alcanzado' })).toBeInTheDocument()
    expect(screen.getByText(/Envíos \(1\)/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /evaluar ahora/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Destinatarios' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /marcar como vista/i }))
    expect(await screen.findByText('Ya la viste')).toBeInTheDocument()
  })

  it('el Ingeniero evalúa ahora y agrega un destinatario', async () => {
    const { fetchSpy } = renderApp(
      '/alertas',
      {
        'GET /reservoirs': [tule],
        'GET /alerts': [],
        'GET /alerts/recipients': [],
        'POST /alerts/evaluate': { TULE: { nuevas: 1, actualizadas: 0, resueltas: 0, notificaciones: 1 } },
        'POST /alerts/recipients': (body) => ({ status: 201, body: { id: 1, ...(body as object) } }),
      },
      makeMe('INGENIERO'),
    )
    await userEvent.click(await screen.findByRole('button', { name: /evaluar ahora/i }))
    expect(await screen.findByText(/TULE: 1 nuevas/)).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText(/nombre o cargo/i), 'Director Estadal')
    await userEvent.type(screen.getByLabelText(/correo electrónico/i), 'director@hidrica-zulia.com')
    await userEvent.click(screen.getByRole('button', { name: /agregar/i }))
    const call = fetchSpy.mock.calls.find(([u, i]) => String(u).endsWith('/alerts/recipients') && i?.method === 'POST')
    expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({ name: 'Director Estadal', channel: 'correo', min_severity: 'alerta' })
  })
})

describe('Reportes (M10)', () => {
  it('descarga el boletín en el formato elegido', async () => {
    const { fetchSpy } = renderApp('/reportes', { 'GET /reservoirs': [tule] }, makeMe('GERENCIA'))
    const original = fetchSpy.getMockImplementation()!
    fetchSpy.mockImplementation(async (input, init) => {
      if (String(input).includes('/reports/bulletin')) {
        return new Response(new Blob(['%PDF']), { status: 200, headers: { 'Content-Disposition': 'attachment; filename="boletin_2026-10-31.pdf"' } })
      }
      return original(input, init)
    })
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    const card = (await screen.findByRole('heading', { name: 'Boletín diario' })).closest('section')!
    await userEvent.click(within(card).getByRole('button', { name: /PDF/ }))
    expect(await within(card).findByText('Descargado: boletin_2026-10-31.pdf')).toBeInTheDocument()
    expect(fetchSpy.mock.calls.some(([u]) => String(u).endsWith('/reports/bulletin?format=pdf'))).toBe(true)
  })

  it('el Operador no tiene acceso a reportes', async () => {
    renderApp('/reportes', { 'GET /reservoirs': [tule] }, makeMe('OPERADOR'))
    expect(await screen.findByRole('heading', { name: 'Panel principal' })).toBeInTheDocument()
  })
})

describe('Ayuda (M11)', () => {
  it('filtra el glosario', async () => {
    renderApp('/ayuda', {}, makeMe('OPERADOR'))
    await userEvent.type(await screen.findByLabelText('Buscar término'), 'ndwi')
    expect(screen.getByText('NDWI')).toBeInTheDocument()
    expect(screen.queryByText('Volumen muerto')).not.toBeInTheDocument()
    expect(screen.getByText('¿Por qué el semáforo está gris?')).toBeInTheDocument()
  })
})
