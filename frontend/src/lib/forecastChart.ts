import type { EChartsCoreOption } from 'echarts/core'

import type { Forecast, HistoryResponse } from '../api/types'
import { baseAxis, CHART } from './chartTheme'

const THRESHOLD_NAMES: Record<string, string> = {
  low_critical: 'Crítico bajo',
  low_alert: 'Alerta baja',
  high_alert: 'Alerta alta',
  spill_level: 'Alivio',
  dead_level: 'Volumen muerto',
}

const nf = (v: number) => v.toLocaleString('es-VE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

type Point = HistoryResponse['points'][number]

/** Cota observada + rango histórico (mín–máx del mismo día del año) + proyección p50 con banda p10–p90 + umbrales.
 * Un solo eje (cota). */
export function forecastOption(points: Point[], f: Forecast): EChartsCoreOption {
  const sorted = [...points].sort((a, b) => a.day.localeCompare(b.day))
  const hist = sorted.filter((p) => p.level_m !== null).map((p) => [p.day, p.level_m as number])
  const clim = sorted.filter((p) => p.hist_min !== null && p.hist_max !== null)
  const last = hist[hist.length - 1]
  // La proyección arranca en el último dato observado para que la línea sea continua
  const start = last ? [[last[0], last[1], last[1], last[1]]] : []
  const proj = [...start, ...f.days.map((d) => [d.day, d.level_p10, d.level_p50, d.level_p90])] as [string, number, number, number][]

  const refLines = [
    ...Object.entries(f.thresholds).map(([k, v]) => ({ name: THRESHOLD_NAMES[k] ?? k, yAxis: v })),
    { name: 'Nivel normal', yAxis: f.normal_level },
  ]
  const values = [
    ...hist.map((h) => h[1] as number),
    ...clim.flatMap((c) => [c.hist_min as number, c.hist_max as number]),
    ...proj.flatMap((p) => [p[1], p[3]]),
    ...refLines.map((r) => r.yAxis),
  ]
  const min = Math.floor(Math.min(...values) - 0.5)
  const max = Math.ceil(Math.max(...values) + 0.5)

  return {
    animation: false,
    textStyle: { fontFamily: CHART.font },
    grid: { left: 56, right: 110, top: 64, bottom: 64 },
    legend: {
      top: 0,
      left: 0,
      textStyle: { color: CHART.textSecondary },
      data: ['Cota observada', 'Rango histórico', 'Proyección (mediana)', 'Banda 80 %'],
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line' },
      valueFormatter: (v: unknown) => (typeof v === 'number' ? `${nf(v)} m` : '—'),
    },
    xAxis: { type: 'time', ...baseAxis, splitLine: { show: false } },
    yAxis: { type: 'value', name: 'Cota (m.s.n.m.)', nameTextStyle: { color: CHART.textSecondary }, min, max, ...baseAxis },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 8 }],
    series: [
      // Rango histórico (mín–máx de años anteriores para el mismo día): base invisible + alto apilado, en gris
      {
        name: 'Histórico mínimo',
        type: 'line',
        data: clim.map((c) => [c.day, c.hist_min]),
        stack: 'clima',
        showSymbol: false,
        lineStyle: { opacity: 0 },
        tooltip: { show: false },
        silent: true,
      },
      {
        name: 'Rango histórico',
        type: 'line',
        data: clim.map((c) => [c.day, (c.hist_max as number) - (c.hist_min as number)]),
        stack: 'clima',
        showSymbol: false,
        lineStyle: { opacity: 0 },
        areaStyle: { color: '#94a3b8', opacity: 0.22 },
        itemStyle: { color: '#94a3b8' },
        tooltip: { show: false },
      },
      {
        name: 'Cota observada',
        type: 'line',
        data: hist,
        showSymbol: false,
        lineStyle: { width: 2, color: CHART.series1 },
        itemStyle: { color: CHART.series1 },
        markLine: {
          symbol: 'none',
          silent: true,
          lineStyle: { type: 'dashed', color: CHART.textSecondary, width: 1 },
          label: { position: 'end', formatter: '{b}', color: CHART.textSecondary, fontSize: 11 },
          data: refLines,
        },
      },
      // Banda: base invisible (p10) + alto apilado (p90 − p10)
      {
        name: 'Banda inferior',
        type: 'line',
        data: proj.map((p) => [p[0], p[1]]),
        stack: 'banda',
        showSymbol: false,
        lineStyle: { opacity: 0 },
        tooltip: { show: false },
        silent: true,
      },
      {
        name: 'Banda 80 %',
        type: 'line',
        data: proj.map((p) => [p[0], p[3] - p[1]]),
        stack: 'banda',
        showSymbol: false,
        lineStyle: { opacity: 0 },
        areaStyle: { color: CHART.series2, opacity: CHART.bandOpacity },
        itemStyle: { color: CHART.series2 },
        tooltip: { show: false },
      },
      {
        name: 'Proyección (mediana)',
        type: 'line',
        data: proj.map((p) => [p[0], p[2]]),
        showSymbol: false,
        lineStyle: { width: 2, type: 'dashed', color: CHART.series2 },
        itemStyle: { color: CHART.series2 },
      },
    ],
  }
}

export function forecastAriaLabel(f: Forecast): string {
  const h = f.horizons.map((x) => `a ${x.horizon_days} días ${nf(x.level_p50)} m (entre ${nf(x.level_p10)} y ${nf(x.level_p90)})`).join('; ')
  return `Gráfica de la cota observada y proyectada desde el ${f.origin}: ${h}.`
}
