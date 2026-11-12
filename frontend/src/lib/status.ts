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
