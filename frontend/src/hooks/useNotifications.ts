import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { notificationService } from '../services/notificationService'

/** Shared so callers that patch the bell's cache cannot mistype its key. */
export const notificationKeys = {
  all: ['notifications'] as const,
  unread: ['notifications', 'unread'] as const,
  history: ['notifications', 'history'] as const,
}

export function useUnreadNotifications(enabled: boolean = true) {
  return useQuery({
    queryKey: notificationKeys.unread,
    queryFn: () => notificationService.getUnread(),
    enabled,
    // No polling — fetches on mount and on window focus (tab return).
    // Polling was removed to allow Neon compute to auto-suspend between requests.
  })
}

export function useNotificationHistory(enabled: boolean) {
  return useQuery({
    queryKey: notificationKeys.history,
    queryFn: () => notificationService.getHistory(),
    enabled,
  })
}

export function useMarkAllNotificationsRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => notificationService.markAllRead(),
    onSuccess: () => qc.invalidateQueries({ queryKey: notificationKeys.all }),
  })
}

export function useMarkNotificationRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => notificationService.markRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: notificationKeys.unread }),
  })
}
