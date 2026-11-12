// Formatos para la interfaz (locale es-VE).

/** Formato numérico venezolano (coma decimal, punto de miles). */
export function fmt(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined) return '—'
  return n.toLocaleString('es-VE', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('es-VE', { dateStyle: 'short', timeStyle: 'short' })
}
