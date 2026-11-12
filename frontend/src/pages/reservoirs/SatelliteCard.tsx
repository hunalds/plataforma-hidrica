import { CloudRain, Drop, Info, Plant, Waves } from '@phosphor-icons/react'
import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import { api } from '../../api/client'
import type { SatelliteSummary } from '../../api/types'
import { Metric } from '../../components/status'
import { Card, Spinner } from '../../components/ui'
import { fmt } from '../../lib/format'
import { SAT_HELP } from '../../lib/status'

function dateEs(iso: string | null): string {
  return iso ? new Date(`${iso}T00:00`).toLocaleDateString('es-VE', { dateStyle: 'medium' }) : '—'
}

function Block({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-border p-4">
      <h3 className="flex items-center gap-2 font-heading font-semibold">
        <span aria-hidden="true" className="text-accent">
          {icon}
        </span>
        {title}
      </h3>
      <dl className="mt-3 grid grid-cols-2 gap-3">{children}</dl>
    </section>
  )
}

export function SatelliteCard({ code }: { code: string }) {
  const q = useQuery({ queryKey: ['satellite', code], queryFn: () => api.get<SatelliteSummary>(`/reservoirs/${code}/satellite/summary`) })
  if (q.isPending) return <Spinner label="Cargando indicadores satelitales…" />
  if (q.isError) return null
  const s = q.data
  const empty = s.precipitation_last_day === null && s.soil_moisture_day === null && s.water_area_day === null
  const anomaly = s.precipitation_30d_anomaly_pct
  const waterPct = s.water_area_km2 !== null && s.water_area_reference_km2 ? (s.water_area_km2 / s.water_area_reference_km2) * 100 : null

  return (
    <Card>
      <h2 className="text-xl font-semibold">Indicadores satelitales</h2>
      <p className="text-muted-foreground">Lluvia, humedad del suelo y espejo de agua observados desde el espacio.</p>
      {empty ? (
        <p className="mt-4 text-muted-foreground">Aún no se han descargado datos satelitales para este embalse.</p>
      ) : (
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <Block icon={<CloudRain size={22} />} title="Lluvia en la cuenca">
            <Metric label="Últimos 7 días" value={s.precipitation_7d_mm !== null ? `${fmt(s.precipitation_7d_mm, 0)} mm` : '—'} help={SAT_HELP.rain} />
            <Metric label="Últimos 30 días" value={s.precipitation_30d_mm !== null ? `${fmt(s.precipitation_30d_mm, 0)} mm` : '—'} />
            <Metric
              label="Frente a lo normal"
              value={anomaly !== null ? `${anomaly > 0 ? '+' : ''}${fmt(anomaly, 0)} %` : '—'}
              help={SAT_HELP.anomaly}
            />
            <Metric label="Dato hasta" value={dateEs(s.precipitation_last_day)} />
          </Block>
          <Block icon={<Plant size={22} />} title="Humedad del suelo">
            <Metric label="Actual" value={s.soil_moisture !== null ? `${fmt(s.soil_moisture, 3)} m³/m³` : '—'} help={SAT_HELP.soil} />
            <Metric label="Normal del mes" value={s.soil_moisture_normal !== null ? `${fmt(s.soil_moisture_normal, 3)} m³/m³` : '—'} />
            <Metric label="Dato del" value={dateEs(s.soil_moisture_day)} />
          </Block>
          <Block icon={<Waves size={22} />} title="Espejo de agua">
            <Metric label="Superficie" value={s.water_area_km2 !== null ? `${fmt(s.water_area_km2, 1)} km²` : '—'} help={SAT_HELP.water} />
            <Metric label="Del polígono" value={waterPct !== null ? `${fmt(waterPct, 0)} %` : '—'} />
            <Metric label="NDWI" value={s.ndwi !== null ? fmt(s.ndwi, 2) : '—'} help={SAT_HELP.ndwi} />
            <Metric label="Imagen del" value={dateEs(s.water_area_day)} />
          </Block>
        </div>
      )}
      {(s.geometry_source?.includes('PROVISIONAL') || s.basin_source?.includes('PROVISIONAL')) && (
        <p className="mt-4 flex items-start gap-2 text-sm text-muted-foreground">
          <Info size={18} aria-hidden="true" className="mt-0.5 shrink-0" />
          <span>
            Geometrías provisionales: polígono del embalse de OpenStreetMap y cuenca aproximada con un área de influencia de 20 km.
            Se reemplazarán por las oficiales de MINAGUAS.
          </span>
        </p>
      )}
      <p className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
        <Drop size={14} aria-hidden="true" /> Fuentes: CHIRPS (UCSB), ERA5-Land (ECMWF/Copernicus vía Open-Meteo), Sentinel-2 (ESA) y Landsat (USGS).
      </p>
    </Card>
  )
}
