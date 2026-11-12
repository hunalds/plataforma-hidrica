import type { RouteObject } from 'react-router'

import { MODULES } from './api/types'
import { AnonymousOnly, RequireAuth, RequireImporter, RequirePermission } from './auth/guards'
import { AppShell, AuthLayout } from './components/AppShell'
import { AuditPage } from './pages/admin/AuditPage'
import { UsersPage } from './pages/admin/UsersPage'
import { LoginPage } from './pages/auth/LoginPage'
import { ChangePasswordPage, ForgotPasswordPage, ResetPasswordPage } from './pages/auth/PasswordPages'
import { DailyEntryPage } from './pages/ingest/DailyEntryPage'
import { ImportPage } from './pages/ingest/ImportPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ReservoirDetailPage } from './pages/reservoirs/ReservoirDetailPage'
import { ReservoirsPage } from './pages/reservoirs/ReservoirsPage'
import { ModelsPage } from './pages/ml/ModelsPage'
import { SatellitePage } from './pages/satellite/SatellitePage'
import { StatusPage } from './pages/StatusPage'

export const routes: RouteObject[] = [
  {
    element: <AuthLayout />,
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
    children: [
      {
        element: <AppShell />,
        children: [
          { path: 'cambiar-clave', element: <ChangePasswordPage /> },
          {
            element: <RequirePermission module={MODULES.reservoirs} />,
            children: [
              { index: true, element: <ReservoirsPage /> },
              { path: 'embalses/:code', element: <ReservoirDetailPage /> },
            ],
          },
          {
            element: <RequirePermission module={MODULES.ingest} level="MANAGE" />,
            children: [
              { path: 'registro', element: <DailyEntryPage /> },
              { element: <RequireImporter />, children: [{ path: 'importar', element: <ImportPage /> }] },
            ],
          },
          {
            element: <RequirePermission module={MODULES.prediction} />,
            children: [{ path: 'modelos', element: <ModelsPage /> }],
          },
          {
            element: <RequirePermission module={MODULES.satellite} />,
            children: [{ path: 'satelite', element: <SatellitePage /> }],
          },
          {
            element: <RequirePermission module={MODULES.users} level="MANAGE" />,
            children: [{ path: 'usuarios', element: <UsersPage /> }],
          },
          {
            element: <RequirePermission module={MODULES.audit} />,
            children: [{ path: 'auditoria', element: <AuditPage /> }],
          },
          { path: 'estado', element: <StatusPage /> },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
]
