import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// jsdom reemplaza AbortSignal, pero Request es el de Node (undici) y rechaza esa señal.
// React Router crea un Request con `signal` en cada navegación: en pruebas se omite la señal.
const NodeRequest = globalThis.Request
class TestRequest extends NodeRequest {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    const rest: RequestInit = { ...init }
    delete rest.signal
    super(input, rest)
  }
}
globalThis.Request = TestRequest as typeof Request

// jsdom no dibuja mapas: react-leaflet se reemplaza por contenedores simples (la lógica propia sí se prueba)
vi.mock('react-leaflet', async () => {
  const React = await import('react')
  const Box = ({ children }: { children?: React.ReactNode }) => React.createElement('div', null, children)
  const Layers = Object.assign(Box, { BaseLayer: Box, Overlay: Box })
  return {
    MapContainer: ({ children }: { children?: React.ReactNode }) => React.createElement('div', { 'data-testid': 'mapa' }, children),
    TileLayer: () => null,
    GeoJSON: ({ data }: { data: { features: { properties: { name: string } }[] } }) =>
      React.createElement('ul', null, data.features.map((f) => React.createElement('li', { key: f.properties.name }, f.properties.name))),
    LayersControl: Layers,
  }
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  window.localStorage.clear()
})
