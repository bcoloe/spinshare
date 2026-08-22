import { apiFetch } from './apiClient'
import type { AdminMetricsResponse } from '../types/admin'

export const adminService = {
  metrics(days = 30): Promise<AdminMetricsResponse> {
    return apiFetch(`/admin/metrics?days=${days}`)
  },
}
