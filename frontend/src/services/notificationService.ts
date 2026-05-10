import { apiFetch } from './apiClient'
import type { NotificationResponse } from '../types/notification'

export const notificationService = {
  getUnread(): Promise<NotificationResponse[]> {
    return apiFetch('/notifications')
  },

  getHistory(): Promise<NotificationResponse[]> {
    return apiFetch('/notifications/history')
  },

  markRead(notificationId: number): Promise<NotificationResponse> {
    return apiFetch(`/notifications/${notificationId}/read`, { method: 'POST' })
  },

  markAllRead(): Promise<void> {
    return apiFetch('/notifications/read-all', { method: 'POST' })
  },
}
