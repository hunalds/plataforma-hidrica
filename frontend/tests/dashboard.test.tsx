import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

// ECharts dibuja en <canvas>, que jsdom no tiene: se sustituye por su contenedor accesible.
vi.mock('../src/components/charts/EChart', () => ({
  EChart: ({ label }: { label: string }) => <div role="img" aria-label={label} />,
}))

vi.mock('react-leaflet', async () => {
  const React = await import('react')
  const Box = ({ children }: { children?: React.ReactNode }) => React.createElement('div', null, children)
  return {
    MapContainer: Box,
    TileLayer: () => null,
    GeoJSON: () => null,
    LayersControl: Object.assign(Box, { BaseLayer: Box, Overlay: Box }),
  }
})

import type { MapFeatures } from '../src/api/types'
import { makeMe, renderApp, tule, tuleStatus } from './helpers'

const square = { type: 'Polygon', coordinates: [[[-72.2, 10.8], [-72.0, 10.8], [-72.0, 11.0], [-72.2, 10.8]]] } as GeoJSON.Polygon

const mapData: MapFeatures = {
  reservoirs: {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        geometry: square,
        properties: {
          code: 'TULE',
          name: 'Tulé',
          light: 'amarillo',
          direction: 'escasez',
          light_reason: 'Nivel bajo',
          level_m: 29.4,
          availability_pct: 30.7,
          reserve_days: 122,
          last_day: '2026-10-31',
          is_stale: false,
          precip_30d_mm: 180,
          soil_moisture: 0.3,
          soil_moisture_day: '2026-11-10',
          water_area_km2: 23.7,
          water_area_day: '2026-10-29',
          geometry_source: 'OSM',
        },
      },
    ],
  },
  basins: {
    type: 'FeatureCollection',
    features: [{ type: 'Feature', geometry: square, properties: { code: 'TULE', name: 'Área Tulé', precip_30d_mm: 180, soil_moisture: 0.3, source: 'provisional' } }],
  },
  satellite_source: 'real',
  attribution: 'Polígonos © colaboradores de OpenStreetMap (ODbL)',
}

describe('Panel principal (HU-5.x)', () => {
  it('muestra tarjetas con semáforo, el mapa con capas, alertas y el comparativo', async () => {
    renderApp(
      '/',
      {
        'GET /reservoirs': [tule],
        'GET /reservoirs/status': [tuleStatus],
        'GET /map/features': mapData,
        'GET /dashboard/comparison': [{ reservoir_code: 'TULE', name: 'Tulé', availability: [['2026-10-30', 30.2], ['2026-10-31', 30.7]] }],
        'GET /alerts': [],
      },
      makeMe('GERENCIA'),
    )
    expect(await screen.findByRole('heading', { name: 'Panel principal' })).toBeInTheDocument()
    expect(await screen.findByText(/último dato 2026-10-31/)).toBeInTheDocument()
    expect(await screen.findByRole('radio', { name: 'Lluvia de 30 días' }, { timeout: 8000 })).toBeChecked()
    expect(await screen.findByText('Crítico o aliviando')).toBeInTheDocument()
    expect(await screen.findByText('No hay alertas activas.')).toBeInTheDocument()

    // El comparativo ofrece vista de tabla (accesibilidad / bajo contraste)
    await userEvent.click(await screen.findByRole('button', { name: 'Ver como tabla' }))
    const table = screen.getByRole('table', { name: 'Disponibilidad reciente por embalse' })
    expect(within(table).getByRole('rowheader', { name: 'Tulé' }).closest('tr')).toHaveTextContent('30,7 %')
  })

  it('la escala del mapa cambia al elegir humedad del suelo', async () => {
    renderApp('/mapa', { 'GET /reservoirs': [tule], 'GET /map/features': mapData }, makeMe('OPERADOR'))
    await userEvent.click(await screen.findByRole('radio', { name: 'Humedad del suelo' }))
    expect(screen.getByLabelText('Escala de humedad')).toHaveTextContent('m³/m³')
  })

  it('el panel muestra las alertas activas con su severidad', async () => {
    renderApp(
      '/',
      {
        'GET /reservoirs': [tule],
        'GET /alerts': [
          {
            id: 1,
            reservoir_code: 'TULE',
            reservoir_name: 'Tulé',
            kind: 'proyectada',
            direction: 'escasez',
            severity: 'critica',
            threshold: 'low_critical',
            threshold_level: 27.5,
            title: 'Se proyecta nivel bajo crítico en 30 días',
            message: '',
            value: 0.62,
            horizon_days: 30,
            probability: 0.62,
            event_day: '2026-11-30',
            created_at: '2026-11-12T10:00:00Z',
            updated_at: '2026-11-12T10:00:00Z',
            resolved_at: null,
            acknowledged_by_me: false,
            acknowledgements: [],
            deliveries: [],
          },
        ],
      },
      makeMe('OPERADOR'),
    )
    expect(await screen.findByText('Se proyecta nivel bajo crítico en 30 días')).toBeInTheDocument()
    expect(screen.getByText('Crítica')).toBeInTheDocument()
  })
})
