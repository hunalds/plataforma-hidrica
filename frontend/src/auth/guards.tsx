import { Navigate, Outlet, useLocation } from 'react-router'

import type { AccessLevel, ModuleKey } from '../api/types'
import { Spinner } from '../components/ui'
import { useAuth } from './AuthContext'

/** Exige sesión iniciada; si el usuario debe cambiar su contraseña lo envía a hacerlo primero. */
export function RequireAuth() {
  const { status, user } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <Spinner label="Cargando sesión…" fullScreen />
  if (status === 'anonymous') return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (user?.must_change_password && location.pathname !== '/cambiar-clave') {
    return <Navigate to="/cambiar-clave" replace />
  }
  return <Outlet />
}

/** Oculta una ruta a los roles sin permiso (el backend igual lo impide con 403). */
export function RequirePermission({ module, level = 'READ' }: { module: ModuleKey; level?: AccessLevel }) {
  const { can } = useAuth()
  if (!can(module, level)) return <Navigate to="/" replace />
  return <Outlet />
}

/** Para /login y similares: si ya hay sesión, ir al inicio. */
export function AnonymousOnly() {
  const { status } = useAuth()
  if (status === 'loading') return <Spinner label="Cargando…" fullScreen />
  if (status === 'authenticated') return <Navigate to="/" replace />
  return <Outlet />
}

/** Importar archivos: el Operador tiene M4 = gestionar, pero "solo registro manual" (matriz §6). */
export function RequireImporter() {
  const { user } = useAuth()
  if (user?.role === 'OPERADOR') return <Navigate to="/registro" replace />
  return <Outlet />
}
