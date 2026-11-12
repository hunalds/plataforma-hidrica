import { Brain, CheckCircle, CircleNotch, PushPin, PushPinSlash, XCircle } from '@phosphor-icons/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, ApiError } from '../../api/client'
import { MODEL_LABELS, MODULES, type Job, type MLModelInfo } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Button, Card, PageHeader, Spinner } from '../../components/ui'
import { fmt, fmtDateTime } from '../../lib/format'

const NAMES: Record<string, string> = { TULE: 'Tulé', MANUELOTE: 'Manuelote', TRES_RIOS: 'Tres Ríos' }

function TrainPanel() {
  const qc = useQueryClient()
  const jobs = useQuery({
    queryKey: ['ml-jobs'],
    queryFn: () => api.get<Job[]>('/ml/jobs'),
    refetchInterval: (q) => (q.state.data?.some((j) => j.status === 'EN_CURSO' || j.status === 'PENDIENTE') ? 3000 : false),
  })
  const train = useMutation({
    mutationFn: () => api.post<Job>('/ml/train', {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ml-jobs'] }),
  })
  const running = jobs.data?.find((j) => j.status === 'EN_CURSO' || j.status === 'PENDIENTE')
  const last = jobs.data?.[0]
  if (last?.status === 'TERMINADA') void qc.invalidateQueries({ queryKey: ['ml-models'] })
  return (
    <Card>
      <h2 className="text-xl font-semibold">Reentrenar</h2>
      <p className="mt-1 text-muted-foreground">
        Entrena los cuatro modelos de cada embalse con todos los datos y repite el backtesting de los últimos 4 años. Tarda
        alrededor de 25 minutos; corre en segundo plano.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Button onClick={() => train.mutate()} loading={train.isPending} disabled={!!running}>
          <Brain size={20} aria-hidden="true" /> Reentrenar todos los embalses
        </Button>
        {train.isError && <Alert tone="error">{(train.error as ApiError).message}</Alert>}
      </div>
      {last && (
        <div className="mt-4" aria-live="polite">
          <p className="flex items-center gap-2 text-sm">
            {running ? (
              <CircleNotch size={18} className="animate-spin text-accent" aria-hidden="true" />
            ) : last.status === 'TERMINADA' ? (
              <CheckCircle size={18} weight="fill" className="text-status-normal" aria-hidden="true" />
            ) : (
              <XCircle size={18} weight="fill" className="text-status-critical" aria-hidden="true" />
            )}
            Último entrenamiento: {fmtDateTime(last.created_at)} · {last.message}
          </p>
          {running && (
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted" role="progressbar" aria-label="Avance del entrenamiento" aria-valuenow={Math.round(running.progress * 100)} aria-valuemin={0} aria-valuemax={100}>
              <div className="h-full bg-accent" style={{ width: `${running.progress * 100}%` }} />
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

export function ModelsPage() {
  const { can } = useAuth()
  const qc = useQueryClient()
  const manage = can(MODULES.prediction, 'MANAGE')
  const models = useQuery({ queryKey: ['ml-models'], queryFn: () => api.get<MLModelInfo[]>('/ml/models') })
  const pin = useMutation({
    mutationFn: ({ id, on }: { id: number; on: boolean }) => api.post<MLModelInfo>(`/ml/models/${id}/${on ? 'pin' : 'unpin'}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['ml-models'] })
      void qc.invalidateQueries({ queryKey: ['forecast'] })
    },
  })

  // Solo el modelo más reciente de cada tipo por embalse (los anteriores quedan en el registro)
  const latest = new Map<string, MLModelInfo>()
  for (const m of models.data ?? []) {
    const key = `${m.reservoir_code}:${m.kind}`
    const prev = latest.get(key)
    if (!prev || prev.created_at < m.created_at) latest.set(key, m)
  }
  const byReservoir = new Map<string, MLModelInfo[]>()
  for (const m of latest.values()) byReservoir.set(m.reservoir_code, [...(byReservoir.get(m.reservoir_code) ?? []), m])

  return (
    <div className="space-y-6">
      <PageHeader
        title="Modelos de predicción"
        description="Comparación de los modelos con pruebas sobre años pasados (backtesting). El sistema usa el de menor error; el Ingeniero puede fijar otro."
      />
      {manage && <TrainPanel />}
      {models.isPending && <Spinner label="Cargando modelos…" />}
      {models.data?.length === 0 && <Alert tone="info">Aún no hay modelos entrenados.</Alert>}
      {pin.isError && <Alert tone="error">{(pin.error as ApiError).message}</Alert>}
      {[...byReservoir.entries()].map(([code, list]) => (
        <Card key={code}>
          <h2 className="text-xl font-semibold">{NAMES[code] ?? code}</h2>
          <p className="text-sm text-muted-foreground">
            Datos {list[0].data_from} a {list[0].data_to} · años de prueba {list[0].test_years.join(', ')} · {list[0].data_source}
          </p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <caption className="sr-only">Error de los modelos de {NAMES[code] ?? code} por horizonte</caption>
              <thead className="border-b border-border text-muted-foreground">
                <tr>
                  <th scope="col" className="py-2 pr-3">Modelo</th>
                  <th scope="col" className="py-2 pr-3 text-right">Error a 30 d (hm³)</th>
                  <th scope="col" className="py-2 pr-3 text-right">Error a 60 d</th>
                  <th scope="col" className="py-2 pr-3 text-right">Error a 90 d</th>
                  <th scope="col" className="py-2 pr-3 text-right">Error en cota a 90 d (m)</th>
                  <th scope="col" className="py-2 pr-3 text-right">R² a 90 d</th>
                  <th scope="col" className="py-2 pr-3 text-right">Cobertura banda</th>
                  <th scope="col" className="py-2">Estado</th>
                </tr>
              </thead>
              <tbody>
                {list
                  .sort((a, b) => a.score - b.score)
                  .map((m) => {
                    const h = (n: number) => m.metrics.find((x) => x.horizonte === n)
                    return (
                      <tr key={m.id} className={`border-b border-border last:border-0 ${m.active ? 'bg-status-normal-bg' : ''}`}>
                        <th scope="row" className="py-2 pr-3 text-left font-semibold">{MODEL_LABELS[m.kind] ?? m.kind}</th>
                        <td className="py-2 pr-3 text-right tabular-nums">{fmt(h(30)?.MAE_hm3)}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{fmt(h(60)?.MAE_hm3)}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{fmt(h(90)?.MAE_hm3)}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{fmt(h(90)?.MAE_cota_m)}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{fmt(h(90)?.R2)}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{fmt(h(90)?.['cobertura_80_%'], 0)} %</td>
                        <td className="py-2">
                          <div className="flex flex-wrap items-center gap-2">
                            {m.active && <span className="rounded-full bg-status-normal px-2 py-0.5 text-xs font-semibold text-white">En uso</span>}
                            {m.pinned && <span className="text-xs font-semibold">Fijado</span>}
                            {manage && (
                              <Button variant="secondary" className="min-h-9 px-2 text-sm" onClick={() => pin.mutate({ id: m.id, on: !m.pinned })}>
                                {m.pinned ? <PushPinSlash size={16} aria-hidden="true" /> : <PushPin size={16} aria-hidden="true" />}
                                {m.pinned ? 'Soltar' : 'Fijar'}
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Error = error absoluto medio del volumen en las pruebas (menor es mejor). Cobertura = % de veces que el valor real cayó
            dentro de la banda (ideal 80 %).
          </p>
        </Card>
      ))}
    </div>
  )
}
