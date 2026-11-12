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
