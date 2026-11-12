import { Eye, EyeSlash } from '@phosphor-icons/react'
import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'

import { ApiError } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Button, Card, TextField } from '../../components/ui'
import { es } from '../../i18n/es'

export function LoginPage() {
  const { login, notice } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const user = await login(email.trim(), password)
      const from = (location.state as { from?: string } | null)?.from
      navigate(user.must_change_password ? '/cambiar-clave' : (from ?? '/'), { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo conectar con el servidor.')
      setPassword('')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <h1 className="text-2xl font-semibold">{es.login.title}</h1>
      <p className="mt-1 text-muted-foreground">{es.login.intro}</p>

      <div className="mt-4 space-y-3" aria-live="polite">
        {notice && !error && <Alert tone="info">{notice}</Alert>}
        {error && <Alert tone="error">{error}</Alert>}
      </div>

      <form onSubmit={onSubmit} className="mt-4 space-y-4" noValidate>
        <TextField
          label={es.login.email}
          type="email"
          name="email"
          autoComplete="username"
          inputMode="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <div className="relative">
          <TextField
            label={es.login.password}
            type={show ? 'text' : 'password'}
            name="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <button
            type="button"
            onClick={() => setShow((v) => !v)}
            className="absolute bottom-0 right-0 inline-flex min-h-11 min-w-11 cursor-pointer items-center justify-center text-muted-foreground hover:text-foreground"
            aria-label={show ? es.login.hidePassword : es.login.showPassword}
            aria-pressed={show}
          >
            {show ? <EyeSlash size={22} aria-hidden="true" /> : <Eye size={22} aria-hidden="true" />}
          </button>
        </div>
        <Button type="submit" loading={loading} className="w-full" disabled={!email || !password}>
          {es.login.submit}
        </Button>
      </form>
      <p className="mt-4 text-center">
        <Link to="/recuperar" className="font-semibold text-accent underline underline-offset-4 hover:text-primary">
          {es.login.forgot}
        </Link>
      </p>
    </Card>
  )
}
