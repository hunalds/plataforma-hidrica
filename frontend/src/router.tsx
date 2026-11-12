import { lazy, Suspense, type ReactNode } from 'react'
import type { RouteObject } from 'react-router'

import { MODULES } from './api/types'
import { AnonymousOnly, RequireAuth, RequireImporter, RequirePermission } from './auth/guards'
import { AppShell, AuthLayout } from './components/AppShell'
import { Spinner } from './components/ui'
import { LoginPage } from './pages/auth/LoginPage'
import { ChangePasswordPage, ForgotPasswordPage, ResetPasswordPage } from './pages/auth/PasswordPages'
import { ErrorPage } from './pages/ErrorPage'
import { NotFoundPage } from './pages/NotFoundPage'

// Cada pantalla se descarga solo cuando se visita (requisito: panel en menos de 3 s)
const page = <T extends Record<string, unknown>>(loader: () => Promise<T>, name: keyof T) =>
  lazy(() => loader().then((m) => ({ default: m[name] as React.ComponentType })))

const DashboardPage = page(() => import('./pages/dashboard/DashboardPage'), 'DashboardPage')
const MapPage = page(() => import('./pages/dashboard/DashboardPage'), 'MapPage')
const ReservoirsPage = page(() => import('./pages/reservoirs/ReservoirsPage'), 'ReservoirsPage')
const ReservoirDetailPage = page(() => import('./pages/reservoirs/ReservoirDetailPage'), 'ReservoirDetailPage')
const DailyEntryPage = page(() => import('./pages/ingest/DailyEntryPage'), 'DailyEntryPage')
const ImportPage = page(() => import('./pages/ingest/ImportPage'), 'ImportPage')
const ModelsPage = page(() => import('./pages/ml/ModelsPage'), 'ModelsPage')
const SatellitePage = page(() => import('./pages/satellite/SatellitePage'), 'SatellitePage')
const UsersPage = page(() => import('./pages/admin/UsersPage'), 'UsersPage')
const AuditPage = page(() => import('./pages/admin/AuditPage'), 'AuditPage')
const StatusPage = page(() => import('./pages/StatusPage'), 'StatusPage')
const AlertsPage = page(() => import('./pages/alerts/AlertsPage'), 'AlertsPage')
const ReportsPage = page(() => import('./pages/reports/ReportsPage'), 'ReportsPage')
const HelpPage = page(() => import('./pages/help/HelpPage'), 'HelpPage')

const s = (el: ReactNode) => <Suspense fallback={<Spinner label="Cargando…" />}>{el}</Suspense>

export const routes: RouteObject[] = [
  {
    element: <AuthLayout />,
    errorElement: <ErrorPage />,
    children: [
      {
        element: <AnonymousOnly />,
        children: [
          { path: 'login', element: <LoginPage /> },
          { path: 'recuperar', element: <ForgotPasswordPage /> },
        ],
      },
      // El enlace del correo funciona con o sin sesión abierta
      { path: 'restablecer', element: <ResetPasswordPage /> },
    ],
  },
  {
    element: <RequireAuth />,
    errorElement: <ErrorPage />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: 'cambiar-clave', element: <ChangePasswordPage /> },
          {
            element: <RequirePermission module={MODULES.dashboard} />,
            children: [{ index: true, element: s(<DashboardPage />) }],
          },
          {
            element: <RequirePermission module={MODULES.map} />,
            children: [{ path: 'mapa', element: s(<MapPage />) }],
          },
          {
            element: <RequirePermission module={MODULES.reservoirs} />,
            children: [
              { path: 'embalses', element: s(<ReservoirsPage />) },
              { path: 'embalses/:code', element: s(<ReservoirDetailPage />) },
            ],
          },
          {
            element: <RequirePermission module={MODULES.ingest} level="MANAGE" />,
            children: [
              { path: 'registro', element: s(<DailyEntryPage />) },
              { element: <RequireImporter />, children: [{ path: 'importar', element: s(<ImportPage />) }] },
            ],
          },
          {
            element: <RequirePermission module={MODULES.prediction} />,
            children: [{ path: 'modelos', element: s(<ModelsPage />) }],
          },
          {
            element: <RequirePermission module={MODULES.satellite} />,
            children: [{ path: 'satelite', element: s(<SatellitePage />) }],
          },
          {
            element: <RequirePermission module={MODULES.alerts} />,
            children: [{ path: 'alertas', element: s(<AlertsPage />) }],
          },
          {
            element: <RequirePermission module={MODULES.reports} level="MANAGE" />,
            children: [{ path: 'reportes', element: s(<ReportsPage />) }],
          },
          {
            element: <RequirePermission module={MODULES.help} />,
            children: [{ path: 'ayuda', element: s(<HelpPage />) }],
          },
          {
            element: <RequirePermission module={MODULES.users} level="MANAGE" />,
            children: [{ path: 'usuarios', element: s(<UsersPage />) }],
          },
          {
            element: <RequirePermission module={MODULES.audit} />,
            children: [{ path: 'auditoria', element: s(<AuditPage />) }],
          },
          { path: 'estado', element: s(<StatusPage />) },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
]
