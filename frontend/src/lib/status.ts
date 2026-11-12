// Textos del semáforo y ayudas de los indicadores (lenguaje sencillo, sin tecnicismos sin explicar).
import type { Direction, Light } from '../api/types'

export function lightLabel(light: Light, direction: Direction): string {
  if (light === 'gris') return 'Sin datos'
  if (light === 'verde') return 'Normal'
  if (direction === 'inundacion_alivio') return light === 'rojo' ? 'Aliviando' : 'Alerta por nivel alto'
  return light === 'rojo' ? 'Crítico por escasez' : 'Alerta por escasez'
}

export const HELP = {
  level: 'Cota: altura del agua en metros sobre el nivel del mar (m.s.n.m.), leída en el limnímetro.',
  volume: 'Volumen total almacenado, calculado con la curva cota–volumen (hm³ = millones de m³).',
  useful: 'Volumen útil: agua que realmente se puede extraer (volumen actual menos el volumen muerto).',
  availability: 'Disponibilidad: volumen útil como porcentaje de la capacidad útil. Más de 100 % significa que el embalse está aliviando.',
  reserveDays: 'Días de reserva: cuántos días alcanzaría el agua útil si se siguiera extrayendo lo mismo de hoy (salida + gasto ecológico) sin lluvias.',
  spill: 'Alivio: agua almacenada por encima del nivel normal, que el embalse vierte por el aliviadero.',
  change7d: 'Cambio de la cota respecto a hace 7 días. Positivo = está subiendo.',
}

export const SAT_HELP = {
  rain: 'Lluvia acumulada sobre el área que aporta agua al embalse, estimada por satélite (CHIRPS).',
  anomaly: 'Comparación con el promedio de los mismos 30 días en los años anteriores. Negativo = más seco de lo normal.',
  soil: 'Humedad del suelo (capa superficial): un suelo húmedo deja escurrir más lluvia hacia el embalse.',
  water: 'Superficie del espejo de agua medida en la última imagen satelital sin nubes (Sentinel-2 o Landsat).',
  ndwi: 'Índice de agua (NDWI): mayor que 0 indica agua. Sirve para seguir los cambios del espejo de agua.',
}

export const VARIABLE_LABELS: Record<string, string> = {
  precipitacion_mm: 'Precipitación (mm/día)',
  humedad_suelo_m3m3: 'Humedad del suelo (m³/m³)',
  superficie_agua_km2: 'Superficie de agua (km²)',
  ndwi_medio: 'NDWI medio',
}

export const KIND_LABELS: Record<string, string> = {
  precipitacion: 'Precipitación (CHIRPS)',
  humedad_suelo: 'Humedad del suelo (ERA5-Land)',
  agua: 'NDWI y superficie de agua (Sentinel-2 / Landsat)',
}
