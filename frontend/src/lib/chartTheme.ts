// Parámetros de gráficas (skill dataviz). Colores de serie validados con validate_palette.js:
// categóricos 1 (azul) y 2 (naranja) de la paleta de referencia. Los umbrales van en tinta neutra
// con etiqueta escrita: los colores de estado quedan reservados al semáforo.
export const CHART = {
  surface: '#fcfcfb',
  textPrimary: '#0b0b0b',
  textSecondary: '#52514e',
  grid: '#e5e7eb',
  axis: '#cbd5e1',
  series1: '#2a78d6', // histórico / observado
  series2: '#eb6834', // proyección
  bandOpacity: 0.18,
  font: "'Source Sans 3', ui-sans-serif, system-ui, sans-serif",
}

export const baseAxis = {
  axisLine: { lineStyle: { color: CHART.axis } },
  axisTick: { show: false },
  axisLabel: { color: CHART.textSecondary, fontFamily: CHART.font },
  splitLine: { lineStyle: { color: CHART.grid } },
}
