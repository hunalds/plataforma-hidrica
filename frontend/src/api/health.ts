import { useQuery } from '@tanstack/react-query'

import { ApiError, apiGet } from './client'

export interface Health {
  status: 'ok' | 'degraded'
  version: string
  environment: string
  database: 'ok' | 'error'
  postgis: string | null
  detail: string | null
}

/** Devuelve el estado aunque la API responda 503 (base de datos caída): ese cuerpo también es útil. */
export async function fetchHealth(): Promise<Health> {
  try {
    return await apiGet<Health>('/health')
  } catch (err) {
    if (err instanceof ApiError && err.status === 503 && err.body) return err.body as Health
    throw err
  }
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  })
}
