import type { RouteObject } from 'react-router'

import { MODULES } from './api/types'
import { AnonymousOnly, RequireAuth, RequirePermission } from './auth/guards'
import { AppShell, AuthLayout } from './components/AppShell'
import { AuditPage } from './pages/admin/AuditPage'
import { UsersPage } from './pages/admin/UsersPage'
import { LoginPage } from './pages/auth/LoginPage'
import { ChangePasswordPage, ForgotPasswordPage, ResetPasswordPage } from './pages/auth/PasswordPages'
import { NotFoundPage } from './pages/NotFoundPage'
import { ReservoirDetailPage } from './pages/reservoirs/ReservoirDetailPage'
import { ReservoirsPage } from './pages/reservoirs/ReservoirsPage'
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
