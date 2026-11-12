import { Drop } from '@phosphor-icons/react'
import { Link, Outlet } from 'react-router'

import { es } from '../i18n/es'

export function AppShell() {
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#contenido"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface focus:px-4 focus:py-2 focus:shadow"
      >
        {es.app.skipToContent}
      </a>

      <header className="bg-primary text-on-primary">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:px-6">
          <Drop size={28} weight="fill" aria-hidden="true" className="shrink-0 text-sky-300" />
          <div className="min-w-0">
            <Link to="/" className="font-heading text-lg font-semibold leading-tight text-on-primary">
              {es.app.name}
            </Link>
            <p className="truncate text-sm text-sky-100">{es.app.subtitle}</p>
          </div>
        </div>
      </header>

      <main id="contenido" tabIndex={-1} className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
        <Outlet />
      </main>

      <footer className="border-t border-border bg-surface">
        <p className="mx-auto max-w-6xl px-4 py-3 text-sm text-muted-foreground sm:px-6">{es.app.footer}</p>
      </footer>
    </div>
  )
}
