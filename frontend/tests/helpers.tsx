import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { vi } from 'vitest'

import { tokens } from '../src/api/client'
import type { Me, Reservoir, ReservoirStatus, Role } from '../src/api/types'
import { AuthProvider } from '../src/auth/AuthContext'
import { routes } from '../src/router'

type Handler = (body: unknown, url: URL) => { status?: number; body: unknown }
export type Routes = Record<string, Handler | unknown>

const PERMISSIONS: Record<Role, Me['permissions']> = {
  GERENCIA: { M1_auditoria: 'READ', M2_usuarios: 'MANAGE', M3_embalses: 'READ', M4_ingesta: 'READ', M7_panel: 'READ', M11_ayuda: 'READ', M12_calculos: 'READ' },
  INGENIERO: { M3_embalses: 'MANAGE', M4_ingesta: 'MANAGE', M7_panel: 'READ', M11_ayuda: 'READ', M12_calculos: 'MANAGE' },
  OPERADOR: { M3_embalses: 'READ', M4_ingesta: 'MANAGE', M7_panel: 'READ', M11_ayuda: 'READ', M12_calculos: 'READ' },
}

export function makeMe(role: Role, extra: Partial<Me> = {}): Me {
  return {
    id: 1,
    email: `${role.toLowerCase()}@hidrica-zulia.com`,
    full_name: `Usuario ${role}`,
    role,
    is_active: true,
    must_change_password: false,
    reservoir_codes: ['TULE'],
    last_login_at: null,
    created_at: '2026-11-12T00:00:00Z',
    permissions: PERMISSIONS[role],
    ...extra,
  }
}

export const tule: Reservoir = {
  code: 'TULE',
  name: 'Tulé',
  basin: null,
  description: null,
  records_start: '2005-01-01',
  normal_level: 33.4,
  dead_level: 26.6,
  has_geometry: false,
  has_basin_geometry: false,
  thresholds: { low_critical: null, low_alert: 29, high_alert: null, spill_level: null },
  current_curve: null,
  dead_volume_hm3: null,
  normal_volume_hm3: null,
  useful_capacity_hm3: null,
}

export const tuleStatus: ReservoirStatus = {
  reservoir_code: 'TULE',
  reservoir_name: 'Tulé',
  last_day: '2026-10-31',
  last_reading_time: '08:00:00',
  days_since_last: 1,
  is_stale: false,
  level_m: 29.4,
  volume_hm3: 74.2,
  dead_volume_hm3: 27.4,
  normal_volume_hm3: 180,
  useful_volume_hm3: 46.8,
  useful_capacity_hm3: 152.6,
  availability_pct: 30.7,
  reserve_days: 122,
  spill_hm3: 0,
  is_spilling: false,
  inflow_m3s: 6.1,
  outflow_m3s: 4.0,
  eco_flow_m3s: 0.4,
  light: 'amarillo',
  direction: 'escasez',
  light_reason: 'Nivel bajo: alerta de escasez',
  thresholds_defined: true,
  level_change_7d_m: -0.12,
  curve_version: 1,
  missing_curve: false,
}

export function tokenResponse(user: Me) {
  return { access_token: 'acceso', refresh_token: 'renovar', token_type: 'bearer', expires_in: 900, user }
}

/** Simula la API: claves "MÉTODO /ruta" (sin query). Las rutas no definidas responden 404. */
export function mockApi(routes: Routes) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = new URL(String(input))
    const key = `${init?.method ?? 'GET'} ${url.pathname}`
    const raw = init?.body
    const body = typeof raw === 'string' ? JSON.parse(raw) : raw
    const handler = routes[key]
    if (handler === undefined) {
      return new Response(JSON.stringify({ detail: { code: 'NOT_FOUND', message: `Sin simular: ${key}` } }), { status: 404 })
    }
    const result = typeof handler === 'function' ? (handler as Handler)(body, url) : { body: handler }
    return new Response(JSON.stringify(result.body), {
      status: result.status ?? 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
}

/** Renderiza la app completa. Con `as` se simula una sesión ya iniciada (refresh token guardado). */
export function renderApp(path: string, routesMock: Routes = {}, as?: Me) {
  tokens.clear()
  // Respuestas por defecto de los endpoints que consultan casi todas las pantallas
  const fullRoutes: Routes = {
    'GET /reservoirs/status': [],
    'GET /reservoirs/TULE/status': tuleStatus,
    'GET /reservoirs/TULE/measurements': [],
    'GET /reservoirs/TULE/balance': { reservoir_code: 'TULE', date_from: '2026-10-01', date_to: '2026-10-31', days: [], totals: {}, note: '' },
    ...routesMock,
  }
  if (as) {
    window.localStorage.setItem('ph.refresh', 'renovar')
    fullRoutes['POST /auth/refresh'] ??= tokenResponse(as)
  }
  const fetchSpy = mockApi(fullRoutes)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  const utils = render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  )
  return { ...utils, router, fetchSpy }
}
