// Componentes base accesibles (design tokens de index.css; ver docs/design-system.md).
import { CheckCircle, CircleNotch, Info, Warning, XCircle } from '@phosphor-icons/react'
import { useId, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from 'react'

export function Spinner({ label, fullScreen = false }: { label: string; fullScreen?: boolean }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex items-center justify-center gap-3 text-muted-foreground ${fullScreen ? 'min-h-dvh' : 'py-10'}`}
    >
      <CircleNotch size={24} className="animate-spin" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

type Variant = 'primary' | 'secondary' | 'danger'
const variants: Record<Variant, string> = {
  primary: 'bg-accent text-on-accent hover:bg-primary',
  secondary: 'border border-border bg-surface text-foreground hover:bg-muted',
  danger: 'bg-status-critical text-white hover:opacity-90',
}

export function Button({
  variant = 'primary',
  loading = false,
  children,
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  return (
    <button
      type="button"
      {...props}
      disabled={props.disabled || loading}
      aria-busy={loading || undefined}
      className={`inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-md px-4 font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${className}`}
    >
      {loading && <CircleNotch size={18} className="animate-spin" aria-hidden="true" />}
      {children}
    </button>
  )
}

interface FieldProps {
  label: string
  hint?: string
  error?: string
}

export function TextField({ label, hint, error, id, className = '', ...props }: FieldProps & InputHTMLAttributes<HTMLInputElement>) {
  const auto = useId()
  const fieldId = id ?? auto
  const describedBy = [hint && `${fieldId}-hint`, error && `${fieldId}-error`].filter(Boolean).join(' ') || undefined
  return (
    <div className={className}>
      <label htmlFor={fieldId} className="mb-1 block font-semibold">
        {label}
        {props.required && <span className="text-status-critical" aria-hidden="true"> *</span>}
      </label>
      <input
        id={fieldId}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...props}
        className={`min-h-11 w-full rounded-md border bg-surface px-3 text-base ${error ? 'border-status-critical' : 'border-border'}`}
      />
      {hint && (
        <p id={`${fieldId}-hint`} className="mt-1 text-sm text-muted-foreground">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${fieldId}-error`} className="mt-1 text-sm font-semibold text-status-critical">
          {error}
        </p>
      )}
    </div>
  )
}

export function SelectField({
  label,
  hint,
  id,
  children,
  className = '',
  ...props
}: FieldProps & SelectHTMLAttributes<HTMLSelectElement>) {
  const auto = useId()
  const fieldId = id ?? auto
  return (
    <div className={className}>
      <label htmlFor={fieldId} className="mb-1 block font-semibold">
        {label}
      </label>
      <select
        id={fieldId}
        {...props}
        className="min-h-11 w-full cursor-pointer rounded-md border border-border bg-surface px-3 text-base"
      >
        {children}
      </select>
      {hint && <p className="mt-1 text-sm text-muted-foreground">{hint}</p>}
    </div>
  )
}

type Tone = 'success' | 'warning' | 'error' | 'info'
const tones: Record<Tone, { cls: string; icon: ReactNode }> = {
  success: { cls: 'bg-status-normal-bg text-status-normal border-status-normal', icon: <CheckCircle size={22} weight="fill" /> },
  warning: { cls: 'bg-status-alert-bg text-status-alert border-status-alert', icon: <Warning size={22} weight="fill" /> },
  error: { cls: 'bg-status-critical-bg text-status-critical border-status-critical', icon: <XCircle size={22} weight="fill" /> },
  info: { cls: 'bg-muted text-primary border-accent', icon: <Info size={22} weight="fill" /> },
}

export function Alert({ tone, title, children }: { tone: Tone; title?: string; children?: ReactNode }) {
  const t = tones[tone]
  return (
    <div role={tone === 'error' ? 'alert' : 'status'} className={`flex items-start gap-3 rounded-lg border-l-4 p-4 ${t.cls}`}>
      <span className="mt-0.5 shrink-0" aria-hidden="true">
        {t.icon}
      </span>
      <div className="min-w-0 text-foreground">
        {title && <p className="font-semibold">{title}</p>}
        {children}
      </div>
    </div>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-lg border border-border bg-surface p-4 shadow-sm sm:p-5 ${className}`}>{children}</section>
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold sm:text-3xl">{title}</h1>
        {description && <p className="mt-1 max-w-prose text-muted-foreground">{description}</p>}
      </div>
      {actions}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-surface p-8 text-center">
      <p className="font-heading text-lg font-semibold">{title}</p>
      {children && <div className="mt-2 text-muted-foreground">{children}</div>}
    </div>
  )
}
