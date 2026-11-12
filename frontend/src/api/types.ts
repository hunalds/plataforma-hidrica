// Tipos de la API (reflejan los esquemas Pydantic del backend).

export type Role = 'GERENCIA' | 'INGENIERO' | 'OPERADOR'
export type AccessLevel = 'READ' | 'MANAGE'

export const MODULES = {
  audit: 'M1_auditoria',
  users: 'M2_usuarios',
  reservoirs: 'M3_embalses',
  ingest: 'M4_ingesta',
  satellite: 'M5_satelite',
  prediction: 'M6_prediccion',
  dashboard: 'M7_panel',
  map: 'M8_mapa',
  alerts: 'M9_alertas',
  reports: 'M10_reportes',
  help: 'M11_ayuda',
  calcs: 'M12_calculos',
} as const
export type ModuleKey = (typeof MODULES)[keyof typeof MODULES]

export interface User {
  id: number
  email: string
  full_name: string
  role: Role
  is_active: boolean
  must_change_password: boolean
  reservoir_codes: string[]
  last_login_at: string | null
  created_at: string
}

export interface Me extends User {
  permissions: Partial<Record<ModuleKey, AccessLevel>>
}

export interface Thresholds {
  low_critical: number | null
  low_alert: number | null
  high_alert: number | null
  spill_level: number | null
  updated_at?: string | null
}

export interface CurveSummary {
  id: number
  version: number
  valid_from: string
  source_filename: string | null
  notes: string | null
  created_at: string
  points: number
  min_elevation: number
  max_elevation: number
  max_volume_hm3: number
}

export interface Reservoir {
  code: string
  name: string
  basin: string | null
  description: string | null
  records_start: string | null
  normal_level: number
  dead_level: number
  has_geometry: boolean
  has_basin_geometry: boolean
  thresholds: Thresholds
  current_curve: CurveSummary | null
  dead_volume_hm3: number | null
  normal_volume_hm3: number | null
  useful_capacity_hm3: number | null
}

export interface AuditEntry {
  id: number
  created_at: string
  user_id: number | null
  user_email: string | null
  action: string
  entity: string | null
  entity_id: string | null
  old_value: Record<string, unknown> | null
  new_value: Record<string, unknown> | null
  ip: string | null
}

export interface Page<T> {
  items: T[]
  total: number
}

export const ROLE_LABELS: Record<Role, string> = {
  GERENCIA: 'Gerencia',
  INGENIERO: 'Ingeniero / Analista',
  OPERADOR: 'Operador',
}

// --- Iteración 2: movimiento diario, estado operativo e importación ---

export type Light = 'verde' | 'amarillo' | 'rojo' | 'gris'
export type Direction = 'normal' | 'escasez' | 'inundacion_alivio'

export interface ReservoirStatus {
  reservoir_code: string
  reservoir_name: string
  last_day: string | null
  last_reading_time: string | null
  days_since_last: number | null
  is_stale: boolean
  level_m: number | null
  volume_hm3: number | null
  dead_volume_hm3: number | null
  normal_volume_hm3: number | null
  useful_volume_hm3: number | null
  useful_capacity_hm3: number | null
  availability_pct: number | null
  reserve_days: number | null
  spill_hm3: number | null
  is_spilling: boolean | null
  inflow_m3s: number | null
  outflow_m3s: number | null
  eco_flow_m3s: number | null
  light: Light
  direction: Direction
  light_reason: string
  thresholds_defined: boolean
  level_change_7d_m: number | null
  curve_version: number | null
  missing_curve: boolean
}

export interface Measurement {
  day: string
  reading_time: string | null
  level_m: number
  volume_hm3: number | null
  volume_source: 'REPORTADO' | 'CURVA' | null
  inflow_m3s: number | null
  outflow_m3s: number | null
  eco_flow_m3s: number | null
  gate_opening_pct: number | null
  intake_m3s: number | null
  notes: string | null
  quality_flags: string[] | null
  source: 'MANUAL' | 'IMPORT' | 'SQL'
  created_at: string
  useful_volume_hm3: number | null
  availability_pct: number | null
  reserve_days: number | null
  spill_hm3: number | null
}

export interface QualityIssue {
  severity: 'error' | 'aviso'
  code: string
  message: string
  row: number | null
  reservoir: string | null
  day: string | null
  field: string | null
}

export interface ImportBatch {
  id: string
  filename: string
  status: 'PREVIEW' | 'CONFIRMED' | 'DISCARDED'
  created_at: string
  confirmed_at: string | null
  summary: {
    filas_leidas: number
    filas_validas: number
    filas_con_error: number
    errores: number
    avisos: number
    por_embalse: Record<string, { desde: string; hasta: string; filas_validas: number; nuevas: number; existentes: number; dias_faltantes: number }>
  }
  issues: QualityIssue[]
  issues_total: number
  sample: (Partial<Measurement> & { reservoir_code: string })[]
}

export interface BalanceDay {
  day: string
  level_m: number
  volume_hm3: number | null
  inflow_hm3: number
  outflow_hm3: number
  eco_hm3: number
  net_hm3: number
  observed_change_hm3: number | null
  spill_estimate_hm3: number
  residual_hm3: number | null
}

export interface Balance {
  reservoir_code: string
  date_from: string
  date_to: string
  days: BalanceDay[]
  totals: Record<string, number | null>
  note: string
}

// --- Iteración 3: datos satelitales ---

export interface SatelliteSummary {
  reservoir_code: string
  precipitation_7d_mm: number | null
  precipitation_30d_mm: number | null
  precipitation_30d_normal_mm: number | null
  precipitation_30d_anomaly_pct: number | null
  precipitation_last_day: string | null
  soil_moisture: number | null
  soil_moisture_day: string | null
  soil_moisture_normal: number | null
  water_area_km2: number | null
  water_area_day: string | null
  water_area_source: string | null
  water_area_reference_km2: number | null
  ndwi: number | null
  geometry_source: string | null
  basin_source: string | null
}

export type JobStatus = 'PENDIENTE' | 'EN_CURSO' | 'TERMINADA' | 'FALLIDA'

export interface Job {
  id: string
  kind: string
  params: { tipo: string; embalses: string[]; desde: string; hasta: string }
  status: JobStatus
  progress: number
  message: string | null
  result: { guardadas: number; con_valor: number } | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface Coverage {
  reservoir_code: string
  variable: string
  source: string
  observations: number
  with_value: number
  good: number
  first_day: string | null
  last_day: string | null
}

export interface SatelliteSource {
  clave: string
  nombre: string
  variables: string[]
  acceso: string
  resolucion: string
  atribucion: string
}

// --- Iteración 4: predicción ---

export interface ForecastDay {
  day: string
  volume_p10: number
  volume_p50: number
  volume_p90: number
  level_p10: number
  level_p50: number
  level_p90: number
}

export interface ForecastHorizon {
  horizon_days: number
  date: string
  level_p50: number
  level_p10: number
  level_p90: number
  volume_p50: number
  useful_volume_p50: number
  availability_pct_p50: number | null
  reserve_days_p50: number | null
  spill_probability: number
  will_spill: boolean
}

export interface ForecastProbability {
  threshold: string
  label: string
  level: number
  direction: 'bajo' | 'sobre'
  horizon_days: number
  probability: number
}

export interface Forecast {
  reservoir_code: string
  origin: string
  model: { id: number; kind: string; version: string; pinned: boolean; score_mae_hm3: number; data_source: string; trained_at: string }
  days: ForecastDay[]
  horizons: ForecastHorizon[]
  probabilities: ForecastProbability[]
  importance: { variable: string; descripcion: string; peso: number }[]
  thresholds: Record<string, number>
  normal_level: number
}

export interface MLModelInfo {
  id: number
  reservoir_code: string
  kind: string
  version_tag: string
  data_from: string
  data_to: string
  n_days: number
  data_source: string
  test_years: number[]
  params: Record<string, unknown>
  metrics: { horizonte: number; MAE_hm3: number; RMSE_hm3: number; 'MAPE_%': number; R2: number; MAE_cota_m: number; 'cobertura_80_%': number }[]
  importance: Record<string, number> | null
  score: number
  train_seconds: number
  pinned: boolean
  active: boolean
  created_at: string
}

export const MODEL_LABELS: Record<string, string> = {
  persistencia: 'Persistencia (línea base)',
  estacional: 'Estacional (línea base)',
  xgboost: 'XGBoost',
  lstm: 'LSTM (red neuronal)',
}
