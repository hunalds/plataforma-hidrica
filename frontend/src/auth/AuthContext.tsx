import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { api, refreshSession, setSessionLostHandler, tokens, type TokenResponse } from '../api/client'
import type { AccessLevel, Me, ModuleKey } from '../api/types'

/** Cierre de sesión por inactividad en el navegador (el backend también lo aplica al renovar). */
export const IDLE_MINUTES = 30

type Status = 'loading' | 'authenticated' | 'anonymous'

interface AuthState {
  status: Status
  user: Me | null
  /** Motivo del último cierre de sesión automático, para mostrarlo en el login. */
  notice: string | null
  login: (email: string, password: string) => Promise<Me>
  logout: (notice?: string) => Promise<void>
  applyTokens: (t: TokenResponse<Me>) => void
  can: (module: ModuleKey, level?: AccessLevel) => boolean
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>('loading')
  const [user, setUser] = useState<Me | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const applyTokens = useCallback((t: TokenResponse<Me>) => {
    tokens.set(t)
    setUser(t.user)
    setStatus('authenticated')
    setNotice(null)
  }, [])

  const clear = useCallback((message?: string) => {
    tokens.clear()
    setUser(null)
    setStatus('anonymous')
    setNotice(message ?? null)
  }, [])

  // Al cargar la página: intentar recuperar la sesión con el refresh token guardado
  useEffect(() => {
    let cancelled = false
    refreshSession<Me>().then((t) => {
      if (cancelled) return
      if (t) applyTokens(t)
      else clear()
    })
    return () => {
      cancelled = true
    }
  }, [applyTokens, clear])

  useEffect(() => {
    setSessionLostHandler(() => clear('Tu sesión expiró. Inicia sesión nuevamente.'))
    return () => setSessionLostHandler(null)
  }, [clear])

  const login = useCallback(
    async (email: string, password: string) => {
      const t = await api.post<TokenResponse<Me>>('/auth/login', { email, password })
      applyTokens(t)
      return t.user
    },
    [applyTokens],
  )

  const logout = useCallback(
    async (message?: string) => {
      const refresh = tokens.refresh
      if (refresh) await api.post('/auth/logout', { refresh_token: refresh }).catch(() => undefined)
      clear(message)
    },
    [clear],
  )

  // Inactividad: cualquier interacción reinicia el contador
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => {
    if (status !== 'authenticated') return
    const reset = () => {
      window.clearTimeout(timer.current)
      timer.current = window.setTimeout(
        () => void logout(`Tu sesión se cerró tras ${IDLE_MINUTES} minutos de inactividad.`),
        IDLE_MINUTES * 60_000,
      )
    }
    const events = ['pointerdown', 'keydown', 'scroll', 'touchstart'] as const
    events.forEach((e) => window.addEventListener(e, reset, { passive: true }))
    reset()
    return () => {
      window.clearTimeout(timer.current)
      events.forEach((e) => window.removeEventListener(e, reset))
    }
  }, [status, logout])

  const can = useCallback(
    (module: ModuleKey, level: AccessLevel = 'READ') => {
      const granted = user?.permissions[module]
      if (!granted) return false
      return level === 'READ' || granted === 'MANAGE'
    },
    [user],
  )

  const value = useMemo(
    () => ({ status, user, notice, login, logout, applyTokens, can }),
    [status, user, notice, login, logout, applyTokens, can],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return ctx
}
