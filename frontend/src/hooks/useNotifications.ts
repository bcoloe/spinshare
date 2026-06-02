import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { notificationService } from '../services/notificationService'

export function useUnreadNotifications() {
  return useQuery({
    queryKey: ['notifications', 'unread'],
    queryFn: () => notificationService.getUnread(),
    // No polling — fetches on mount and on window focus (tab return).
    // Polling was removed to allow Neon compute to auto-suspend between requests.
  })
}

export function useNotificationHistory(enabled: boolean) {
  return useQuery({
    queryKey: ['notifications', 'history'],
    queryFn: () => notificationService.getHistory(),
    enabled,
  })
}

export function useMarkAllNotificationsRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => notificationService.markAllRead(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications', 'unread'] }),
  })
}

export function useMarkNotificationRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => notificationService.markRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications', 'unread'] }),
  })
}
