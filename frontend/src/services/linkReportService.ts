import { apiFetch } from './apiClient'
import type {
  AdminLinkReportItem,
  LinkReportCreate,
  LinkReportResponse,
  LinkReportStatus,
} from '../types/linkReport'

export const linkReportService = {
  /** Any signed-in user may file a report; editing the link stays admin-only. */
  submit(albumId: number, data: LinkReportCreate): Promise<LinkReportResponse> {
    return apiFetch(`/albums/${albumId}/link-reports`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  list(status: LinkReportStatus = 'open'): Promise<AdminLinkReportItem[]> {
    return apiFetch(`/admin/link-reports?status=${status}`)
  },

  openCount(): Promise<{ open_count: number }> {
    return apiFetch('/admin/link-reports/count')
  },

  resolve(reportId: number): Promise<LinkReportResponse> {
    return apiFetch(`/admin/link-reports/${reportId}/resolve`, { method: 'POST' })
  },

  dismiss(reportId: number, note?: string | null): Promise<LinkReportResponse> {
    return apiFetch(`/admin/link-reports/${reportId}/dismiss`, {
      method: 'POST',
      body: JSON.stringify({ note: note ?? null }),
    })
  },
}
