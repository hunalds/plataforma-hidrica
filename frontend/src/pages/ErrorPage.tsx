import { WarningOctagon } from '@phosphor-icons/react'
import { isRouteErrorResponse, useRouteError } from 'react-router'

/** Pantalla amable para errores inesperados (en lugar del mensaje técnico por defecto). */
export function ErrorPage() {
  const error = useRouteError()
  const detail = isRouteErrorResponse(error) ? `${error.status} ${error.statusText}` : error instanceof Error ? error.message : String(error)
  return (
    <main className="mx-auto flex min-h-dvh max-w-xl flex-col justify-center gap-4 p-6">
      <WarningOctagon size={48} className="text-status-critical" aria-hidden="true" />
      <h1 className="text-2xl font-semibold">Algo salió mal</h1>
      <p className="text-muted-foreground">
        Ocurrió un error inesperado en esta pantalla. Recarga la página; si se repite, informa al equipo técnico el detalle de abajo.
      </p>
      <pre className="overflow-auto rounded-md bg-muted p-3 text-sm">{detail}</pre>
      <div className="flex gap-3">
        <button type="button" onClick={() => window.location.reload()} className="min-h-11 cursor-pointer rounded-md bg-accent px-4 font-semibold text-on-accent">
          Recargar
        </button>
        <a href="/" className="inline-flex min-h-11 items-center rounded-md border border-border px-4 font-semibold">
          Ir al inicio
        </a>
      </div>
    </main>
  )
}
