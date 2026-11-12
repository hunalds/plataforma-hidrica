import { Bell, Brain, ChartBar, ClipboardText, FileText, Question, Drop, FileArrowUp, Gauge, GlobeHemisphereWest, List, MapTrifold, NotePencil, SignOut, UserCircle, Users, Waves, X } from '@phosphor-icons/react'
import { useEffect, useState, type ComponentType } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router'

import { MODULES, ROLE_LABELS, type ModuleKey, type Role } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { es } from '../i18n/es'

interface NavItem {
  to: string
  label: string
  icon: ComponentType<{ size?: number; 'aria-hidden'?: boolean | 'true' }>
  module?: ModuleKey
  level?: 'READ' | 'MANAGE'
  hideFor?: Role[]
}

// Solo se muestran los módulos ya construidos; los demás se agregan en sus iteraciones.
const NAV: NavItem[] = [
  { to: '/', label: es.nav.dashboard, icon: ChartBar, module: MODULES.dashboard },
  { to: '/mapa', label: es.nav.map, icon: MapTrifold, module: MODULES.map },
  { to: '/embalses', label: es.nav.reservoirs, icon: Waves, module: MODULES.reservoirs },
  { to: '/registro', label: es.nav.dailyEntry, icon: NotePencil, module: MODULES.ingest, level: 'MANAGE' },
  { to: '/importar', label: es.nav.import, icon: FileArrowUp, module: MODULES.ingest, level: 'MANAGE', hideFor: ['OPERADOR'] },
  { to: '/alertas', label: es.nav.alerts, icon: Bell, module: MODULES.alerts },
  { to: '/reportes', label: es.nav.reports, icon: FileText, module: MODULES.reports, level: 'MANAGE' },
  { to: '/modelos', label: es.nav.models, icon: Brain, module: MODULES.prediction },
  { to: '/satelite', label: es.nav.satellite, icon: GlobeHemisphereWest, module: MODULES.satellite },
  { to: '/usuarios', label: es.nav.users, icon: Users, module: MODULES.users },
  { to: '/auditoria', label: es.nav.audit, icon: ClipboardText, module: MODULES.audit },
  { to: '/ayuda', label: es.nav.help, icon: Question, module: MODULES.help },
  { to: '/estado', label: es.nav.status, icon: Gauge },
]

export function AppShell() {
  const { user, can, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const location = useLocation()
  useEffect(() => setOpen(false), [location.pathname])

  const items = NAV.filter((i) => (!i.module || can(i.module, i.level)) && !(user && i.hideFor?.includes(user.role)))

  const navList = (
    <ul className="flex flex-col gap-1">
      {items.map(({ to, label, icon: Icon }) => (
        <li key={to}>
          <NavLink
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex min-h-11 items-center gap-3 rounded-md px-3 font-semibold transition-colors ${
                isActive ? 'bg-accent text-on-accent' : 'text-foreground hover:bg-muted'
              }`
            }
          >
            <Icon size={22} aria-hidden="true" />
            {label}
          </NavLink>
        </li>
      ))}
    </ul>
  )

  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#contenido"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:shadow"
      >
        {es.app.skipToContent}
      </a>

      <header className="sticky top-0 z-30 bg-primary text-on-primary">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3 sm:px-6">
          <button
            type="button"
            className="inline-flex min-h-11 min-w-11 cursor-pointer items-center justify-center rounded-md hover:bg-white/10 lg:hidden"
            aria-label={open ? es.nav.closeMenu : es.nav.openMenu}
            aria-expanded={open}
            aria-controls="menu-principal"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X size={24} aria-hidden="true" /> : <List size={24} aria-hidden="true" />}
          </button>
          <Drop size={28} weight="fill" aria-hidden="true" className="shrink-0 text-sky-300" />
          <div className="min-w-0 flex-1">
            <Link to="/" className="font-heading text-lg font-semibold leading-tight text-on-primary">
              {es.app.name}
            </Link>
            <p className="hidden truncate text-sm text-sky-100 sm:block">{es.app.subtitle}</p>
          </div>
          {user && (
            <div className="flex items-center gap-2">
              <div className="hidden text-right text-sm leading-tight md:block">
                <p className="font-semibold">{user.full_name}</p>
                <p className="text-sky-100">{ROLE_LABELS[user.role]}</p>
              </div>
              <UserCircle size={32} aria-hidden="true" className="hidden md:block" />
              <button
                type="button"
                onClick={() => void logout()}
                className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-md px-3 font-semibold hover:bg-white/10"
              >
                <SignOut size={22} aria-hidden="true" />
                <span className="hidden sm:inline">{es.nav.logout}</span>
                <span className="sr-only sm:hidden">{es.nav.logout}</span>
              </button>
            </div>
          )}
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-7xl flex-1 gap-6 px-4 sm:px-6">
        {/* Escritorio: barra lateral */}
        <nav aria-label={es.nav.label} className="hidden w-56 shrink-0 py-6 lg:block">
          {navList}
        </nav>
        {/* Móvil y tableta: panel desplegable */}
        {open && (
          <nav
            id="menu-principal"
            aria-label={es.nav.label}
            className="fixed inset-x-0 top-[68px] z-20 border-b border-border bg-surface p-4 shadow-lg lg:hidden"
          >
            {navList}
          </nav>
        )}
        <main id="contenido" tabIndex={-1} className="min-w-0 flex-1 py-6 sm:py-8">
          <Outlet />
        </main>
      </div>

      <footer className="border-t border-border bg-surface">
        <p className="mx-auto max-w-7xl px-4 py-3 text-sm text-muted-foreground sm:px-6">{es.app.footer}</p>
      </footer>
    </div>
  )
}

/** Layout para pantallas sin sesión (login, recuperación). */
export function AuthLayout() {
  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <header className="bg-primary text-on-primary">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-4 sm:px-6">
          <Drop size={28} weight="fill" aria-hidden="true" className="text-sky-300" />
          <div>
            <p className="font-heading text-lg font-semibold">{es.app.name}</p>
            <p className="text-sm text-sky-100">{es.app.subtitle}</p>
          </div>
        </div>
      </header>
      <main id="contenido" className="flex flex-1 items-start justify-center px-4 py-10 sm:items-center">
        <div className="w-full max-w-md">
          <Outlet />
        </div>
      </main>
      <footer className="px-4 py-3 text-center text-sm text-muted-foreground">{es.app.footer}</footer>
    </div>
  )
}
