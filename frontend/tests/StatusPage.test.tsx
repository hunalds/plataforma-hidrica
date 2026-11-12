import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it, vi } from 'vitest'

import { routes } from '../src/router'

function renderAt(path = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

function mockFetch(status: number, body: unknown) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }),
  )
}

const okBody = {
  status: 'ok',
  version: '0.1.0',
  environment: 'development',
  database: 'ok',
  postgis: '3.6.2',
  detail: null,
}

describe('Página de estado', () => {
  it('muestra "API conectada" y la versión de PostGIS cuando /health responde 200', async () => {
    const fetchSpy = mockFetch(200, okBody)
    renderAt('/')
    expect(await screen.findByText('API conectada')).toBeInTheDocument()
    expect(screen.getByText('3.6.2')).toBeInTheDocument()
    expect(fetchSpy).toHaveBeenCalledWith(expect.stringMatching(/\/health$/), expect.anything())
  })

  it('muestra el estado degradado cuando la base de datos no responde (503)', async () => {
    mockFetch(503, { ...okBody, status: 'degraded', database: 'error', postgis: null, detail: 'No se pudo conectar a la base de datos' })
    renderAt('/')
    expect(await screen.findByText('API activa, base de datos no disponible')).toBeInTheDocument()
    expect(screen.getByText('No se pudo conectar a la base de datos')).toBeInTheDocument()
    expect(screen.getByText('Con fallas')).toBeInTheDocument()
  })

  it('muestra "Sin conexión" si el servidor no responde y permite reintentar', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    renderAt('/')
    expect(await screen.findByText('Sin conexión con la API')).toBeInTheDocument()

    fetchSpy.mockResolvedValue(new Response(JSON.stringify(okBody), { status: 200 }))
    await userEvent.click(screen.getByRole('button', { name: /reintentar/i }))
    expect(await screen.findByText('API conectada')).toBeInTheDocument()
  })

  it('incluye un enlace para saltar al contenido (accesibilidad)', () => {
    mockFetch(200, okBody)
    renderAt('/')
    expect(screen.getByRole('link', { name: 'Saltar al contenido principal' })).toHaveAttribute('href', '#contenido')
  })

  it('muestra una página 404 en español para rutas desconocidas', () => {
    mockFetch(200, okBody)
    renderAt('/no-existe')
    expect(screen.getByRole('heading', { name: 'Página no encontrada' })).toBeInTheDocument()
  })
})
