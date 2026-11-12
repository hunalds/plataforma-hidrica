import { DownloadSimple } from '@phosphor-icons/react'
import { useState, type ReactNode } from 'react'

import { api, ApiError } from '../../api/client'
import { useReservoirs } from '../../api/reservoirs'
import { Alert, Button, Card, PageHeader, SelectField, TextField } from '../../components/ui'

type Fmt = 'pdf' | 'xlsx' | 'csv' | 'png' | 'geojson' | 'kml'
const FMT_LABEL: Record<Fmt, string> = { pdf: 'PDF', xlsx: 'Excel', csv: 'CSV', png: 'Imagen PNG', geojson: 'GeoJSON', kml: 'KML' }

const today = () => new Date().toLocaleDateString('en-CA')
const daysAgo = (n: number) => new Date(Date.now() - n * 86_400_000).toLocaleDateString('en-CA')

function ReportCard({ title, description, formats, buildPath, children }: { title: string; description: string; formats: Fmt[]; buildPath: (f: Fmt) => string; children?: ReactNode }) {
  const [busy, setBusy] = useState<Fmt | null>(null)
  const [msg, setMsg] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
  async function get(f: Fmt) {
    setBusy(f)
    setMsg(null)
    try {
      const name = await api.download(buildPath(f))
      setMsg({ tone: 'success', text: `Descargado: ${name}` })
    } catch (e) {
      setMsg({ tone: 'error', text: e instanceof ApiError ? e.message : 'No se pudo generar el reporte.' })
    } finally {
      setBusy(null)
    }
  }
  return (
    <Card>
      <h2 className="text-xl font-semibold">{title}</h2>
      <p className="mt-1 text-muted-foreground">{description}</p>
      {children && <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{children}</div>}
      <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label={`Descargar ${title}`}>
        {formats.map((f) => (
          <Button key={f} variant="secondary" loading={busy === f} disabled={busy !== null} onClick={() => void get(f)}>
            <DownloadSimple size={18} aria-hidden="true" /> {FMT_LABEL[f]}
          </Button>
        ))}
      </div>
      {msg && (
        <div className="mt-3" aria-live="polite">
          <Alert tone={msg.tone}>{msg.text}</Alert>
        </div>
      )}
    </Card>
  )
}

export function ReportsPage() {
  const reservoirs = useReservoirs()
  const first = reservoirs.data?.[0]?.code ?? 'TULE'
  const [day, setDay] = useState('')
  const [predCode, setPredCode] = useState('')
  const [hist, setHist] = useState({ code: '', aFrom: '2024-01-01', aTo: '2024-03-31', bFrom: '2025-01-01', bTo: '2025-03-31' })
  const [cmp, setCmp] = useState({ from: daysAgo(365), to: today() })
  const [al, setAl] = useState({ from: daysAgo(90), to: today() })
  const options = reservoirs.data?.map((r) => (
    <option key={r.code} value={r.code}>
      {r.name}
    </option>
  ))

  return (
    <div className="space-y-6">
      <PageHeader title="Reportes" description="Descarga los reportes en PDF, Excel/CSV, imagen PNG o formatos geográficos (GeoJSON/KML)." />
      <ReportCard
        title="Boletín diario"
        description="Estado de los embalses al último dato: cota, volumen, disponibilidad, días de reserva, caudales, alivio y semáforo (formato inspirado en el Balance Hídrico diario)."
        formats={['pdf', 'xlsx', 'csv', 'png', 'geojson', 'kml']}
        buildPath={(f) => `/reports/bulletin?format=${f}${day ? `&day=${day}` : ''}`}
      >
        <TextField label="Fecha (vacío = último dato)" type="date" value={day} max={today()} onChange={(e) => setDay(e.target.value)} />
      </ReportCard>
      <ReportCard
        title="Predicción por embalse"
        description="Proyección a 30, 60 y 90 días con su rango, días de reserva y probabilidad de cruzar cada umbral."
        formats={['pdf', 'xlsx', 'csv', 'png']}
        buildPath={(f) => `/reports/prediction/${predCode || first}?format=${f}`}
      >
        <SelectField label="Embalse" value={predCode || first} onChange={(e) => setPredCode(e.target.value)}>
          {options}
        </SelectField>
      </ReportCard>
      <ReportCard
        title="Histórico comparativo"
        description="Compara dos períodos del mismo embalse (por ejemplo, la misma temporada en dos años)."
        formats={['pdf', 'xlsx', 'csv', 'png']}
        buildPath={(f) => `/reports/historical/${hist.code || first}?a_from=${hist.aFrom}&a_to=${hist.aTo}&b_from=${hist.bFrom}&b_to=${hist.bTo}&format=${f}`}
      >
        <SelectField label="Embalse" value={hist.code || first} onChange={(e) => setHist({ ...hist, code: e.target.value })}>
          {options}
        </SelectField>
        <TextField label="Período A: desde" type="date" value={hist.aFrom} onChange={(e) => setHist({ ...hist, aFrom: e.target.value })} />
        <TextField label="Período A: hasta" type="date" value={hist.aTo} onChange={(e) => setHist({ ...hist, aTo: e.target.value })} />
        <span className="hidden lg:block" />
        <span className="hidden lg:block" />
        <TextField label="Período B: desde" type="date" value={hist.bFrom} onChange={(e) => setHist({ ...hist, bFrom: e.target.value })} />
        <TextField label="Período B: hasta" type="date" value={hist.bTo} onChange={(e) => setHist({ ...hist, bTo: e.target.value })} />
      </ReportCard>
      <ReportCard
        title="Comparativo entre embalses"
        description="Disponibilidad, cotas y caudales de los embalses en el mismo período."
        formats={['pdf', 'xlsx', 'csv', 'png']}
        buildPath={(f) => `/reports/comparison?date_from=${cmp.from}&date_to=${cmp.to}&format=${f}`}
      >
        <TextField label="Desde" type="date" value={cmp.from} onChange={(e) => setCmp({ ...cmp, from: e.target.value })} />
        <TextField label="Hasta" type="date" value={cmp.to} onChange={(e) => setCmp({ ...cmp, to: e.target.value })} />
      </ReportCard>
      <ReportCard
        title="Registro de alertas"
        description="Alertas del período con su severidad, quién las vio y por qué canales se enviaron."
        formats={['pdf', 'xlsx', 'csv']}
        buildPath={(f) => `/reports/alerts?date_from=${al.from}&date_to=${al.to}&format=${f}`}
      >
        <TextField label="Desde" type="date" value={al.from} onChange={(e) => setAl({ ...al, from: e.target.value })} />
        <TextField label="Hasta" type="date" value={al.to} onChange={(e) => setAl({ ...al, to: e.target.value })} />
      </ReportCard>
    </div>
  )
}
