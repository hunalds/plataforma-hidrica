import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { makeMe, renderApp, tokenResponse } from './helpers'

const okBody = {
  status: 'ok',
  version: '0.1.0',
  environment: 'development',
  database: 'ok',
  postgis: '3.6.2',
  detail: null,
}

describe('Página de estado (HU-0.4)', () => {
  it('muestra "API conectada" y la versión de PostGIS cuando /health responde 200', async () => {
    renderApp('/estado', { 'GET /health': okBody }, makeMe('OPERADOR'))
    expect(await screen.findByText('API conectada')).toBeInTheDocument()
    expect(screen.getByText('3.6.2')).toBeInTheDocument()
  })

  it('muestra el estado degradado cuando la base de datos no responde (503)', async () => {
    renderApp(
      '/estado',
      {
        'GET /health': () => ({
          status: 503,
          body: { ...okBody, status: 'degraded', database: 'error', postgis: null, detail: 'No se pudo conectar a la base de datos' },
        }),
      },
      makeMe('OPERADOR'),
    )
    expect(await screen.findByText('API activa, base de datos no disponible')).toBeInTheDocument()
    expect(screen.getByText('No se pudo conectar a la base de datos')).toBeInTheDocument()
    expect(screen.getByText('Con fallas')).toBeInTheDocument()
  })

  it('muestra "Sin conexión" si el servidor no responde y permite reintentar', async () => {
    const { fetchSpy } = renderApp('/estado', {}, makeMe('OPERADOR'))
    const original = fetchSpy.getMockImplementation()!
    let fail = true
    fetchSpy.mockImplementation(async (input, init) => {
      if (String(input).endsWith('/health')) {
        if (fail) throw new TypeError('Failed to fetch')
        return new Response(JSON.stringify(okBody), { status: 200 })
      }
      if (String(input).endsWith('/auth/refresh')) return new Response(JSON.stringify(tokenResponse(makeMe('OPERADOR'))))
      return original(input, init)
    })
    expect(await screen.findByText('Sin conexión con la API')).toBeInTheDocument()

    fail = false
    await userEvent.click(screen.getByRole('button', { name: /reintentar/i }))
    expect(await screen.findByText('API conectada')).toBeInTheDocument()
    vi.restoreAllMocks()
  })

  it('incluye un enlace para saltar al contenido (accesibilidad)', async () => {
    renderApp('/estado', { 'GET /health': okBody }, makeMe('OPERADOR'))
    expect(await screen.findByRole('link', { name: 'Saltar al contenido principal' })).toHaveAttribute('href', '#contenido')
  })

  it('muestra una página 404 en español para rutas desconocidas', async () => {
    renderApp('/no-existe', {}, makeMe('OPERADOR'))
    expect(await screen.findByRole('heading', { name: 'Página no encontrada' })).toBeInTheDocument()
  })
})
