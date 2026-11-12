// Cliente HTTP con manejo de sesión (JWT).
// - El token de acceso vive solo en memoria.
// - El refresh token se guarda en localStorage para mantener la sesión al recargar la página.
//   (Decisión documentada: en producción se evaluará moverlo a una cookie httpOnly, ver PENDIENTES P-22.)
// - Ante un 401 se intenta renovar la sesión una vez y se repite la petición.

export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

const REFRESH_KEY = 'ph.refresh'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly body: unknown

  constructor(status: number, body: unknown) {
    const detail = (body as { detail?: unknown } | null)?.detail
    let message = `Error ${status}`
    let code = 'HTTP_ERROR'
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
      const d = detail as { code?: string; message?: string }
      message = d.message ?? message
      code = d.code ?? code
    } else if (Array.isArray(detail)) {
      // Errores de validación de FastAPI/Pydantic
      code = 'VALIDATION_ERROR'
      message = detail
        .map((e: { msg?: string }) => (e.msg ?? '').replace(/^Value error, /, ''))
        .filter(Boolean)
        .join(' ')
    }
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.body = body
  }
}

export interface TokenResponse<U = unknown> {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: U
}

let accessToken: string | null = null
let onSessionLost: (() => void) | null = null

function safeStorage(): Storage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

export const tokens = {
  get access() {
    return accessToken
  },
  get refresh(): string | null {
    try {
      return safeStorage()?.getItem(REFRESH_KEY) ?? null
    } catch {
      return null
    }
  },
  set(t: Pick<TokenResponse, 'access_token' | 'refresh_token'>) {
    accessToken = t.access_token
    try {
      safeStorage()?.setItem(REFRESH_KEY, t.refresh_token)
    } catch {
      /* almacenamiento bloqueado: la sesión dura lo que la pestaña */
    }
  },
  clear() {
    accessToken = null
    try {
      safeStorage()?.removeItem(REFRESH_KEY)
    } catch {
      /* nada */
    }
  },
}

/** Lo registra el AuthProvider para volver al login cuando la sesión no se puede renovar. */
export function setSessionLostHandler(handler: (() => void) | null) {
  onSessionLost = handler
}

let refreshing: Promise<TokenResponse | null> | null = null

/** Renueva la sesión con el refresh token. Comparte la misma promesa si hay varias peticiones a la vez. */
export function refreshSession<U = unknown>(): Promise<TokenResponse<U> | null> {
  const refresh = tokens.refresh
  if (!refresh) return Promise.resolve(null)
  refreshing ??= fetch(`${API_URL}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ refresh_token: refresh }),
  })
    .then(async (res) => {
      if (!res.ok) {
        tokens.clear()
        return null
      }
      const data = (await res.json()) as TokenResponse
      tokens.set(data)
      return data
    })
    .catch(() => null)
    .finally(() => {
      refreshing = null
    })
  return refreshing as Promise<TokenResponse<U> | null>
}

type Method = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

async function request<T>(method: Method, path: string, body?: unknown, retry = true): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  let payload: BodyInit | undefined
  if (body instanceof FormData) {
    payload = body
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`

  const res = await fetch(`${API_URL}${path}`, { method, headers, body: payload })
  if (res.status === 401 && retry && !path.startsWith('/auth/login')) {
    const renewed = await refreshSession()
    if (renewed) return request<T>(method, path, body, false)
    onSessionLost?.()
  }
  const data: unknown = res.status === 204 ? null : await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, data)
  return data as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
}

/** Compatibilidad con HU-0.4 (página de estado). */
export const apiGet = api.get
