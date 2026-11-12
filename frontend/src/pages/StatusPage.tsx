import { ArrowClockwise, CheckCircle, Warning, XCircle } from '@phosphor-icons/react'
import type { ReactNode } from 'react'

import { useHealth } from '../api/health'
import { es } from '../i18n/es'

type Tone = 'normal' | 'alert' | 'critical' | 'unknown'

const toneClasses: Record<Tone, string> = {
  normal: 'bg-status-normal-bg text-status-normal border-status-normal',
  alert: 'bg-status-alert-bg text-status-alert border-status-alert',
  critical: 'bg-status-critical-bg text-status-critical border-status-critical',
  unknown: 'bg-status-unknown-bg text-status-unknown border-status-unknown',
}

function Banner({ tone, icon, title, children }: { tone: Tone; icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div role="status" aria-live="polite" className={`flex items-start gap-3 rounded-lg border-l-4 p-4 ${toneClasses[tone]}`}>
      <span className="mt-0.5 shrink-0" aria-hidden="true">
        {icon}
      </span>
      <div>
        <p className="font-heading text-lg font-semibold">{title}</p>
        {children && <div className="mt-1 text-foreground">{children}</div>}
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-wrap justify-between gap-x-4 gap-y-1 border-b border-border py-3 last:border-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-semibold tabular-nums">{value}</dd>
    </div>
  )
}

export function StatusPage() {
  const { data, isPending, isError, isFetching, refetch, dataUpdatedAt } = useHealth()

  let banner: ReactNode
  if (isPending) {
    banner = <Banner tone="unknown" icon={<ArrowClockwise size={24} className="animate-spin" />} title={es.status.checking} />
  } else if (isError) {
    banner = (
      <Banner tone="critical" icon={<XCircle size={24} weight="fill" />} title={es.status.disconnected}>
        {es.status.disconnectedHelp}
      </Banner>
    )
  } else if (data.status === 'ok') {
    banner = <Banner tone="normal" icon={<CheckCircle size={24} weight="fill" />} title={es.status.connected} />
  } else {
    banner = (
      <Banner tone="alert" icon={<Warning size={24} weight="fill" />} title={es.status.degraded}>
        {data.detail}
      </Banner>
    )
  }

  return (
    <section aria-labelledby="titulo-estado" className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 id="titulo-estado" className="text-2xl font-semibold sm:text-3xl">
          {es.status.title}
        </h1>
        <p className="mt-2 text-muted-foreground">{es.status.intro}</p>
      </div>

      {banner}

      {data && (
        <dl className="rounded-lg border border-border bg-surface px-4 shadow-sm">
          <Row label={es.status.database} value={data.database === 'ok' ? es.status.ok : es.status.error} />
          <Row label={es.status.postgis} value={data.postgis ?? '—'} />
          <Row label={es.status.version} value={data.version} />
          <Row label={es.status.environment} value={data.environment} />
          <Row
            label={es.status.lastCheck}
            value={new Date(dataUpdatedAt).toLocaleTimeString('es-VE', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          />
        </dl>
      )}

      <button
        type="button"
        onClick={() => refetch()}
        disabled={isFetching}
        className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-md bg-accent px-5 font-semibold text-on-accent transition-colors hover:bg-primary disabled:cursor-not-allowed disabled:opacity-50"
      >
        <ArrowClockwise size={20} aria-hidden="true" className={isFetching ? 'animate-spin' : undefined} />
        {es.status.retry}
      </button>
    </section>
  )
}
