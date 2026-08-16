import type { NotificationResponse } from '../types/notification'

/**
 * Where clicking a notification should take the user.
 *
 * Returns null when there is nowhere meaningful to go, which is what the bell
 * uses to decide whether the row is clickable at all.
 *
 * Shared by the unread list and the history list — they previously carried
 * copies of this logic, and only one of them got updated whenever a new
 * notification type was added.
 */
export function notificationTarget(n: NotificationResponse): string | null {
  if (!n.group_id) return null

  const params = new URLSearchParams()

  switch (n.type) {
    case 'member_reviewed_album':
      params.set('tab', 'history')
      if (n.album_id) params.set('album', String(n.album_id))
      break

    case 'mentioned_in_chat':
      // Deep-link straight into an open chat overlay rather than dropping the
      // user on the group page to find it themselves.
      params.set('chat', '1')
      break
  }

  const query = params.toString()
  return `/groups/${n.group_id}${query ? `?${query}` : ''}`
}
