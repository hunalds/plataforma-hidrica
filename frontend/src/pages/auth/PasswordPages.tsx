import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { api, ApiError, type TokenResponse } from '../../api/client'
import type { Me } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Button, Card, TextField } from '../../components/ui'
import { es } from '../../i18n/es'

function errorText(err: unknown) {
  return err instanceof ApiError ? err.message : 'No se pudo conectar con el servidor.'
}

/** Nueva contraseña + confirmación, con validación local básica (el backend aplica la política completa). */
function NewPasswordFields({
  value,
  confirm,
  onChange,
  onConfirm,
  mismatch,
}: {
  value: string
  confirm: string
  onChange: (v: string) => void
  onConfirm: (v: string) => void
  mismatch: boolean
}) {
  return (
    <>
      <TextField
        label={es.changePassword.next}
        type="password"
        autoComplete="new-password"
        required
        hint={es.changePassword.policy}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
      <TextField
        label={es.changePassword.confirm}
        type="password"
        autoComplete="new-password"
        required
        value={confirm}
        error={mismatch ? es.changePassword.mismatch : undefined}
        onChange={(e) => onConfirm(e.target.value)}
      />
    </>
  )
}

export function ChangePasswordPage() {
  const { user, applyTokens, logout } = useAuth()
  const navigate = useNavigate()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const mismatch = confirm.length > 0 && next !== confirm

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (next !== confirm) return
    setError(null)
    setLoading(true)
    try {
      const t = await api.post<TokenResponse<Me>>('/auth/change-password', {
        current_password: current,
        new_password: next,
      })
      applyTokens(t)
      navigate('/', { replace: true })
    } catch (err) {
      setError(errorText(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <Card>
        <h1 className="text-2xl font-semibold">{es.changePassword.title}</h1>
        {user?.must_change_password && <p className="mt-1 text-muted-foreground">{es.changePassword.intro}</p>}
        {error && (
          <div className="mt-4">
            <Alert tone="error">{error}</Alert>
          </div>
        )}
        <form onSubmit={onSubmit} className="mt-4 space-y-4">
          <TextField
            label={es.changePassword.current}
            type="password"
            autoComplete="current-password"
            required
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
          <NewPasswordFields value={next} confirm={confirm} onChange={setNext} onConfirm={setConfirm} mismatch={mismatch} />
          <Button type="submit" loading={loading} className="w-full" disabled={!current || !next || mismatch}>
            {es.changePassword.submit}
          </Button>
          <Button variant="secondary" className="w-full" onClick={() => void logout()}>
            {es.nav.logout}
          </Button>
        </form>
      </Card>
    </div>
  )
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const r = await api.post<{ message: string }>('/auth/forgot-password', { email: email.trim() })
      setSent(r.message)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <h1 className="text-2xl font-semibold">{es.forgot.title}</h1>
      <p className="mt-1 text-muted-foreground">{es.forgot.intro}</p>
      <div className="mt-4 space-y-3">
        {sent && <Alert tone="success">{sent}</Alert>}
        {error && <Alert tone="error">{error}</Alert>}
      </div>
      {!sent && (
        <form onSubmit={onSubmit} className="mt-4 space-y-4">
          <TextField
            label={es.login.email}
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Button type="submit" loading={loading} className="w-full" disabled={!email}>
            {es.forgot.submit}
          </Button>
        </form>
      )}
      <p className="mt-4 text-center">
        <Link to="/login" className="font-semibold text-accent underline underline-offset-4 hover:text-primary">
          {es.forgot.back}
        </Link>
      </p>
    </Card>
  )
}

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [done, setDone] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const mismatch = confirm.length > 0 && next !== confirm

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (next !== confirm) return
    setError(null)
    setLoading(true)
    try {
      const r = await api.post<{ message: string }>('/auth/reset-password', { token, new_password: next })
      setDone(r.message)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <h1 className="text-2xl font-semibold">{es.reset.title}</h1>
      <div className="mt-4 space-y-3">
        {!token && <Alert tone="error">{es.reset.missingToken}</Alert>}
        {done && <Alert tone="success">{done}</Alert>}
        {error && <Alert tone="error">{error}</Alert>}
      </div>
      {token && !done && (
        <form onSubmit={onSubmit} className="mt-4 space-y-4">
          <NewPasswordFields value={next} confirm={confirm} onChange={setNext} onConfirm={setConfirm} mismatch={mismatch} />
          <Button type="submit" loading={loading} className="w-full" disabled={!next || mismatch}>
            {es.reset.submit}
          </Button>
        </form>
      )}
      <p className="mt-4 text-center">
        <Link to="/login" className="font-semibold text-accent underline underline-offset-4 hover:text-primary">
          {es.forgot.back}
        </Link>
      </p>
    </Card>
  )
}
