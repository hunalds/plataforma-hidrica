import { useQuery } from '@tanstack/react-query'

import { api } from './client'
import type { Reservoir } from './types'

export function useReservoirs() {
  return useQuery({ queryKey: ['reservoirs'], queryFn: () => api.get<Reservoir[]>('/reservoirs') })
}
