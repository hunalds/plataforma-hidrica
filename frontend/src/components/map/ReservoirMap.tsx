// Mapa geoespacial (M8) con Leaflet y mapas base libres: OpenStreetMap y Sentinel-2 Cloudless (EOX).
// Sin servicios de Google (no disponibles en Venezuela, C-11).
import 'leaflet/dist/leaflet.css'

import type { LatLngBoundsExpression, PathOptions } from 'leaflet'
import { useMemo, useState } from 'react'
import { GeoJSON, LayersControl, MapContainer, TileLayer } from 'react-leaflet'
import { Link } from 'react-router'

import type { MapFeatures, MapReservoirProps } from '../../api/types'
import { fmt } from '../../lib/format'
import { lightLabel } from '../../lib/status'

// Colores de estado del semáforo (mismos tokens que la interfaz)
const LIGHT_FILL: Record<string, string> = { verde: '#15803d', amarillo: '#ca8a04', rojo: '#b91c1c', gris: '#64748b' }

// Escala secuencial de un solo tono (azul) para la lluvia y la humedad: claro → oscuro
const SEQ = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95']

function seqColor(value: number | null, min: number, max: number): string {
  if (value === null) return '#e2e8f0'
  const t = max > min ? (value - min) / (max - min) : 0.5
  return SEQ[Math.min(SEQ.length - 1, Math.max(0, Math.floor(t * SEQ.length)))]
}

// Recuadro aproximado del estado Zulia, solo como vista inicial si aún no hay polígonos cargados
const ZULIA_VIEW: LatLngBoundsExpression = [
  [8.4, -73.4],
  [11.8, -70.7],
]

function boundsOf(fc: GeoJSON.FeatureCollection): LatLngBoundsExpression | null {
  let minLat = 90
  let minLon = 180
  let maxLat = -90
  let maxLon = -180
  const walk = (c: unknown): void => {
    if (Array.isArray(c) && typeof c[0] === 'number') {
      const [lon, lat] = c as number[]
      minLat = Math.min(minLat, lat)
      maxLat = Math.max(maxLat, lat)
      minLon = Math.min(minLon, lon)
      maxLon = Math.max(maxLon, lon)
    } else if (Array.isArray(c)) c.forEach(walk)
  }
  fc.features.forEach((f) => walk((f.geometry as GeoJSON.Polygon).coordinates))
  return minLat <= maxLat ? [[minLat, minLon], [maxLat, maxLon]] : null
}

function popupHtml(p: MapReservoirProps): string {
  const rows: [string, string][] = [
    ['Estado', lightLabel(p.light, p.direction)],
    ['Cota', p.level_m !== null ? `${fmt(p.level_m)} m` : '—'],
    ['Disponibilidad', p.availability_pct !== null ? `${fmt(p.availability_pct, 1)} %` : '—'],
    ['Días de reserva', p.reserve_days !== null ? fmt(p.reserve_days, 0) : '—'],
    ['Lluvia 30 días', p.precip_30d_mm !== null ? `${fmt(p.precip_30d_mm, 0)} mm` : '—'],
    ['Espejo de agua', p.water_area_km2 !== null ? `${fmt(p.water_area_km2, 1)} km²` : '—'],
  ]
  const esc = (s: string) => s.replace(/[&<>"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[ch] as string)
  return `<div style="font-family:inherit;min-width:190px"><strong style="font-size:15px">${esc(p.name)}</strong>
    <table style="margin-top:6px;font-size:13px">${rows.map(([k, v]) => `<tr><td style="color:#52514e;padding-right:8px">${k}</td><td><b>${esc(v)}</b></td></tr>`).join('')}</table>
    ${p.last_day ? `<div style="font-size:12px;color:#52514e;margin-top:4px">Último dato: ${esc(p.last_day)}${p.is_stale ? ' (desactualizado)' : ''}</div>` : ''}
    <a href="/embalses/${encodeURIComponent(p.code)}" style="display:inline-block;margin-top:6px;font-weight:600">Ver detalle →</a></div>`
}

export type Overlay = 'ninguna' | 'lluvia' | 'humedad'

export function ReservoirMap({ data, height = 460 }: { data: MapFeatures; height?: number }) {
  const [overlay, setOverlay] = useState<Overlay>('lluvia')
  const bounds = useMemo(() => boundsOf(data.basins.features.length ? data.basins : data.reservoirs) ?? ZULIA_VIEW, [data])
  const values = data.basins.features.map((f) => (overlay === 'lluvia' ? f.properties.precip_30d_mm : f.properties.soil_moisture))
  const nums = values.filter((v): v is number => v !== null)
  const [vmin, vmax] = nums.length ? [Math.min(...nums), Math.max(...nums)] : [0, 1]

  const basinStyle = (f?: GeoJSON.Feature): PathOptions => {
    const p = f?.properties as MapFeatures['basins']['features'][number]['properties']
    const v = overlay === 'lluvia' ? p.precip_30d_mm : p.soil_moisture
    return overlay === 'ninguna'
      ? { color: '#475569', weight: 1, dashArray: '4 4', fillOpacity: 0 }
      : { color: '#475569', weight: 1, dashArray: '4 4', fillColor: seqColor(v, vmin, vmax), fillOpacity: 0.45 }
  }
  const reservoirStyle = (f?: GeoJSON.Feature): PathOptions => {
    const p = f?.properties as MapReservoirProps
    return { color: '#0b0b0b', weight: 2, fillColor: LIGHT_FILL[p.light] ?? LIGHT_FILL.gris, fillOpacity: 0.8 }
  }

  return (
    <div className="space-y-3">
      <fieldset className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <legend className="sr-only">Capa sobre las áreas de influencia</legend>
        {(
          [
            ['lluvia', 'Lluvia de 30 días'],
            ['humedad', 'Humedad del suelo'],
            ['ninguna', 'Solo contornos'],
          ] as const
        ).map(([k, label]) => (
          <label key={k} className="inline-flex min-h-11 cursor-pointer items-center gap-2">
            <input type="radio" name="capa" className="size-5 cursor-pointer" checked={overlay === k} onChange={() => setOverlay(k)} />
            {label}
          </label>
        ))}
      </fieldset>
      <div className="overflow-hidden rounded-lg border border-border" style={{ height }}>
        <MapContainer bounds={bounds} scrollWheelZoom style={{ height: '100%', width: '100%' }} aria-label="Mapa de los embalses">
          <LayersControl position="topright">
            <LayersControl.BaseLayer checked name="Mapa (OpenStreetMap)">
              <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="© colaboradores de OpenStreetMap" maxZoom={19} />
            </LayersControl.BaseLayer>
            <LayersControl.BaseLayer name="Satélite (Sentinel-2 Cloudless)">
              <TileLayer
                url="https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2023_3857/default/g/{z}/{y}/{x}.jpg"
                attribution="Sentinel-2 cloudless 2023 © EOX IT Services GmbH (contiene datos modificados de Copernicus Sentinel)"
                maxZoom={15}
              />
            </LayersControl.BaseLayer>
            <LayersControl.Overlay checked name="Áreas de influencia">
              <GeoJSON key={`basins-${overlay}`} data={data.basins} style={basinStyle} />
            </LayersControl.Overlay>
            <LayersControl.Overlay checked name="Embalses (semáforo)">
              <GeoJSON
                key={`res-${data.reservoirs.features.map((f) => f.properties.light).join()}`}
                data={data.reservoirs}
                style={reservoirStyle}
                onEachFeature={(f, layer) => {
                  layer.bindPopup(popupHtml(f.properties as MapReservoirProps))
                  layer.bindTooltip((f.properties as MapReservoirProps).name, { sticky: true })
                }}
              />
            </LayersControl.Overlay>
          </LayersControl>
        </MapContainer>
      </div>
      <div className="flex flex-wrap items-start justify-between gap-4 text-sm">
        <ul className="flex flex-wrap gap-x-4 gap-y-1" aria-label="Leyenda del semáforo">
          {(['verde', 'amarillo', 'rojo', 'gris'] as const).map((l) => (
            <li key={l} className="inline-flex items-center gap-2">
              <span aria-hidden="true" className="inline-block size-3 rounded-sm border border-black/40" style={{ background: LIGHT_FILL[l] }} />
              {{ verde: 'Normal', amarillo: 'Alerta', rojo: 'Crítico o aliviando', gris: 'Sin datos' }[l]}
            </li>
          ))}
        </ul>
        {overlay !== 'ninguna' && nums.length > 0 && (
          <div className="flex items-center gap-2" aria-label={`Escala de ${overlay === 'lluvia' ? 'lluvia' : 'humedad'}`}>
            <span>{overlay === 'lluvia' ? `${fmt(vmin, 0)} mm` : fmt(vmin, 2)}</span>
            <span aria-hidden="true" className="flex">
              {SEQ.map((c) => (
                <span key={c} className="inline-block h-3 w-6" style={{ background: c }} />
              ))}
            </span>
            <span>{overlay === 'lluvia' ? `${fmt(vmax, 0)} mm` : `${fmt(vmax, 2)} m³/m³`}</span>
          </div>
        )}
      </div>
      <p className="text-xs text-muted-foreground">
        {data.attribution}. Geometrías provisionales hasta recibir las oficiales de MINAGUAS.{' '}
        <Link to="/embalses" className="underline">Ver lista de embalses</Link>
      </p>
    </div>
  )
}
