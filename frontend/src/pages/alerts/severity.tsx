import { Info, Warning, WarningOctagon } from '@phosphor-icons/react'

import type { Severity } from '../../api/types'

const STYLES: Record<Severity, { cls: string; label: string; icon: React.ReactNode }> = {
  informativa: { cls: 'bg-muted text-primary border-accent', label: 'Informativa', icon: <Info size={16} weight="fill" /> },
  alerta: { cls: 'bg-status-alert-bg text-status-alert border-status-alert', label: 'Alerta', icon: <Warning size={16} weight="fill" /> },
  critica: { cls: 'bg-status-critical-bg text-status-critical border-status-critical', label: 'Crítica', icon: <WarningOctagon size={16} weight="fill" /> },
}

/** Severidad con color + ícono + texto (nunca solo color). */
export function SeverityBadge({ severity }: { severity: Severity }) {
  const s = STYLES[severity]
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-sm font-semibold ${s.cls}`}>
      <span aria-hidden="true">{s.icon}</span>
      {s.label}
    </span>
  )
}
