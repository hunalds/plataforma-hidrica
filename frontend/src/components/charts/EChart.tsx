// Envoltorio mínimo de ECharts (solo los módulos usados, para no inflar el bundle).
import { BarChart, LineChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, LegendComponent, MarkLineComponent, TooltipComponent } from 'echarts/components'
import type { EChartsCoreOption } from 'echarts/core'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { useEffect, useRef, useState } from 'react'

echarts.use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, DataZoomComponent, CanvasRenderer])

export function EChart({ option, height = 360, label }: { option: EChartsCoreOption; height?: number; label: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const chart = useRef<echarts.ECharts | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!ref.current) return
    try {
      chart.current = echarts.init(ref.current, undefined, { renderer: 'canvas' })
    } catch {
      setFailed(true) // navegador sin canvas: se muestra el aviso y la vista de tabla sigue disponible
      return
    }
    const resize = () => chart.current?.resize()
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null
    observer?.observe(ref.current)
    return () => {
      observer?.disconnect()
      try {
        chart.current?.dispose()
      } catch {
        /* el lienzo ya no existe */
      }
      chart.current = null
    }
  }, [])

  useEffect(() => {
    try {
      chart.current?.setOption(option, { notMerge: true })
    } catch {
      setFailed(true)
    }
  }, [option])

  if (failed) {
    return <p className="rounded-md bg-muted p-4 text-muted-foreground">No se pudo dibujar la gráfica en este navegador. Usa la vista de tabla.</p>
  }
  // role="img" + aria-label: el lector de pantalla recibe el resumen; la tabla equivalente va aparte.
  return <div ref={ref} role="img" aria-label={label} style={{ height, width: '100%' }} />
}
