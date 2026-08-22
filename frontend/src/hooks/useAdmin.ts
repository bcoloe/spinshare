import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { adminService } from '../services/adminService'
import { linkReportService } from '../services/linkReportService'
import type { LinkReportCreate, LinkReportStatus } from '../types/linkReport'

export const adminKeys = {
  all: ['admin'] as const,
  linkReports: (status: LinkReportStatus) => ['admin', 'link-reports', status] as const,
  openCount: () => ['admin', 'link-reports', 'count'] as const,
  metrics: (days: number) => ['admin', 'metrics', days] as const,
}

/**
 * Site growth metrics. Cached for five minutes, matching useSiteStats — a
 * dashboard session should be one burst of queries, not one per re-render.
 */
export function useAdminMetrics(days = 30, enabled = true) {
  return useQuery({
    queryKey: adminKeys.metrics(days),
    queryFn: () => adminService.metrics(days),
    staleTime: 5 * 60 * 1000,
    enabled,
  })
}

export function useLinkReports(status: LinkReportStatus, enabled = true) {
  return useQuery({
    queryKey: adminKeys.linkReports(status),
    queryFn: () => linkReportService.list(status),
    enabled,
  })
}

/**
 * Drives the nav badge. Scoped to admins by `enabled` so no other account pays
 * for the request, and left to the default fetch-on-mount/focus behaviour rather
 * than polling, matching how notifications are handled.
 */
export function useOpenLinkReportCount(enabled = true) {
  return useQuery({
    queryKey: adminKeys.openCount(),
    queryFn: () => linkReportService.openCount(),
    enabled,
  })
}

export function useResolveLinkReport() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (reportId: number) => linkReportService.resolve(reportId),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.all }),
  })
}

export function useDismissLinkReport() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reportId, note }: { reportId: number; note?: string | null }) =>
      linkReportService.dismiss(reportId, note),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.all }),
  })
}

export function useSubmitLinkReport(albumId: number) {
  return useMutation({
    mutationFn: (data: LinkReportCreate) => linkReportService.submit(albumId, data),
  })
}
