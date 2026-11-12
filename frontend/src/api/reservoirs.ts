import { useQuery } from '@tanstack/react-query'

import { api } from './client'
import type { Reservoir, ReservoirStatus } from './types'

export function useReservoirs() {
  return useQuery({ queryKey: ['reservoirs'], queryFn: () => api.get<Reservoir[]>('/reservoirs') })
}

/** Estado operativo (último dato + cálculos M12 + semáforo) de los embalses visibles. */
export function useStatuses() {
  return useQuery({ queryKey: ['status'], queryFn: () => api.get<ReservoirStatus[]>('/reservoirs/status') })
}
