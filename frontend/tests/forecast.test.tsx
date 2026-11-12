import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import type { Forecast, MLModelInfo } from '../src/api/types'
import { forecastAriaLabel, forecastOption } from '../src/lib/forecastChart'
import { makeMe, renderApp, tule } from './helpers'

const days = Array.from({ length: 90 }, (_, i) => {
  const d = new Date(Date.UTC(2026, 9, 16 + i)).toISOString().slice(0, 10)
  const l = 29.2 - i * 0.01
  return { day: d, volume_p10: 60, volume_p50: 70, volume_p90: 80, level_p10: l - 0.4, level_p50: l, level_p90: l + 0.4 }
})

export const forecast: Forecast = {
  reservoir_code: 'TULE',
  origin: '2026-10-15',
  model: { id: 7, kind: 'xgboost', version: 'v1', pinned: false, score_mae_hm3: 8.4, data_source: 'hidrologia: base de datos · satelite: sintetico', trained_at: '2026-11-12T10:00:00Z' },
  days,
  horizons: [30, 60, 90].map((h) => ({
    horizon_days: h,
    date: days[h - 1].day,
    level_p50: days[h - 1].level_p50,
    level_p10: days[h - 1].level_p10,
    level_p90: days[h - 1].level_p90,
    volume_p50: 70,
    useful_volume_p50: 43.2,
    availability_pct_p50: 28,
    reserve_days_p50: 110,
    spill_probability: 0.01,
    will_spill: false,
  })),
  probabilities: [
    { threshold: 'low_alert', label: 'Nivel bajo de alerta', level: 29, direction: 'bajo', horizon_days: 30, probability: 0.31 },
    { threshold: 'low_alert', label: 'Nivel bajo de alerta', level: 29, direction: 'bajo', horizon_days: 60, probability: 0.55 },
    { threshold: 'low_alert', label: 'Nivel bajo de alerta', level: 29, direction: 'bajo', horizon_days: 90, probability: 0.72 },
  ],
  importance: [
    { variable: 'volume_rel', descripcion: 'Volumen útil actual (% de la capacidad)', peso: 0.4 },
    { variable: 'precip_90', descripcion: 'Lluvia de los últimos 90 días', peso: 0.2 },
  ],
  thresholds: { low_alert: 29, dead_level: 26.6 },
  normal_level: 33.4,
}

describe('Gráfica de proyección (HU-4.8)', () => {
  it('arma un solo eje con histórico, banda, mediana y umbrales rotulados', () => {
    const hist = [
      { day: '2026-10-14', level_m: 29.3, hist_min: 28, hist_max: 33, hist_mean: 31 },
      { day: '2026-10-15', level_m: 29.21, hist_min: 28.1, hist_max: 33.1, hist_mean: 31.1 },
    ]
    const opt = forecastOption(hist, forecast) as { yAxis: { name: string }; series: { name: string; data: unknown[]; markLine?: { data: { name: string }[] } }[] }
    expect(opt.yAxis.name).toBe('Cota (m.s.n.m.)')
    expect(opt.series.map((s) => s.name)).toEqual([
      'Histórico mínimo',
      'Rango histórico',
      'Cota observada',
      'Banda inferior',
      'Banda 80 %',
      'Proyección (mediana)',
    ])
    expect(opt.series[1].data[0]).toEqual(['2026-10-14', 5]) // alto de la banda histórica = máx − mín
    expect(opt.series[5].data[0]).toEqual(['2026-10-15', 29.21]) // continúa desde el último dato
    expect(opt.series[2].markLine?.data.map((d) => d.name)).toEqual(['Alerta baja', 'Volumen muerto', 'Nivel normal'])
    expect(forecastAriaLabel(forecast)).toMatch(/a 30 días/)
  })
})

describe('Proyección en la ficha (HU-4.8)', () => {
  const routes = { 'GET /reservoirs/TULE': tule, 'GET /reservoirs/TULE/curves': [], 'GET /reservoirs/TULE/forecast': forecast }

  it('muestra el resumen a 30/60/90 días, las probabilidades y la tabla accesible', async () => {
    renderApp('/embalses/TULE', routes, makeMe('OPERADOR'))
    const card = (await screen.findByRole('heading', { name: 'Proyección a 90 días' })).closest('section')!
    expect(within(card).getByRole('region', { name: 'En 30 días' })).toHaveTextContent('110')
    expect(within(card).getByText('72 %')).toBeInTheDocument()
    expect(within(card).getByText(/Lluvia de los últimos 90 días/)).toBeInTheDocument()
    await userEvent.click(within(card).getByRole('button', { name: /tabla/i }))
    expect(within(card).getByRole('table', { name: 'Proyección diaria de la cota' }).querySelectorAll('tbody tr')).toHaveLength(90)
  })

  it('explica cuando aún no hay modelo entrenado', async () => {
    renderApp(
      '/embalses/TULE',
      { ...routes, 'GET /reservoirs/TULE/forecast': () => ({ status: 404, body: { detail: { code: 'NO_FORECAST', message: 'Aún no hay modelos entrenados para este embalse.' } } }) },
      makeMe('OPERADOR'),
    )
    expect(await screen.findByText('Aún no hay modelos entrenados para este embalse.')).toBeInTheDocument()
  })
})

const model = (over: Partial<MLModelInfo>): MLModelInfo => ({
  id: 1,
  reservoir_code: 'TULE',
  kind: 'xgboost',
  version_tag: 'v1',
  data_from: '2005-01-01',
  data_to: '2026-10-15',
  n_days: 7958,
  data_source: 'sintetico',
  test_years: [2022, 2023, 2024, 2025],
  params: {},
  metrics: [30, 60, 90].map((h) => ({ horizonte: h, MAE_hm3: h / 10, RMSE_hm3: 1, 'MAPE_%': 1, R2: 0.8, MAE_cota_m: 0.3, 'cobertura_80_%': 78 })),
  importance: null,
  score: 6,
  train_seconds: 10,
  pinned: false,
  active: false,
  created_at: '2026-11-12T10:00:00Z',
  ...over,
})

describe('Pantalla de modelos (HU-4.8)', () => {
  it('el Ingeniero ve el modelo en uso y puede fijar otro', async () => {
    let pinned = false
    const { fetchSpy } = renderApp(
      '/modelos',
      {
        'GET /ml/jobs': [],
        'GET /ml/models': () => ({ body: [model({ id: 1, kind: 'xgboost', score: 6, active: !pinned }), model({ id: 2, kind: 'persistencia', score: 20, active: pinned, pinned })] }),
        'POST /ml/models/2/pin': () => {
          pinned = true
          return { body: model({ id: 2, kind: 'persistencia', pinned: true, active: true }) }
        },
      },
      makeMe('INGENIERO'),
    )
    const row = (await screen.findByRole('rowheader', { name: 'XGBoost' })).closest('tr')!
    expect(within(row).getByText('En uso')).toBeInTheDocument()
    const persist = screen.getByRole('rowheader', { name: 'Persistencia (línea base)' }).closest('tr')!
    await userEvent.click(within(persist).getByRole('button', { name: /fijar/i }))
    expect(fetchSpy.mock.calls.some(([u, i]) => String(u).endsWith('/ml/models/2/pin') && i?.method === 'POST')).toBe(true)
  })

  it('Gerencia consulta sin botones de gestión', async () => {
    renderApp('/modelos', { 'GET /ml/jobs': [], 'GET /ml/models': [model({ active: true })] }, makeMe('GERENCIA'))
    expect(await screen.findByRole('rowheader', { name: 'XGBoost' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /reentrenar/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /fijar/i })).not.toBeInTheDocument()
  })
})
