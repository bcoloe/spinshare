import { describe, it, expect } from 'vitest'
import { notificationTarget } from './notificationTarget'
import type { NotificationResponse } from '../types/notification'

function makeNotification(overrides: Partial<NotificationResponse> = {}): NotificationResponse {
  return {
    id: 1,
    type: 'new_member_joined',
    message: 'someone joined',
    group_id: 5,
    album_id: null,
    read_at: null,
    created_at: '2026-08-16T12:00:00Z',
    ...overrides,
  }
}

describe('notificationTarget', () => {
  it('returns null when there is no group to navigate to', () => {
    expect(notificationTarget(makeNotification({ group_id: null }))).toBeNull()
  })

  it('links a generic notification to the group page', () => {
    expect(notificationTarget(makeNotification())).toBe('/groups/5')
  })

  it('opens the chat overlay for a mention', () => {
    const target = notificationTarget(makeNotification({ type: 'mentioned_in_chat' }))
    expect(target).toBe('/groups/5?chat=1')
  })

  it('links a review notification to the history tab with the album focused', () => {
    const target = notificationTarget(
      makeNotification({ type: 'member_reviewed_album', album_id: 99 }),
    )
    expect(target).toBe('/groups/5?tab=history&album=99')
  })

  it('omits the album param when a review notification has no album', () => {
    const target = notificationTarget(makeNotification({ type: 'member_reviewed_album' }))
    expect(target).toBe('/groups/5?tab=history')
  })

  it('returns null for a mention with no group, rather than a bare chat link', () => {
    const target = notificationTarget(
      makeNotification({ type: 'mentioned_in_chat', group_id: null }),
    )
    expect(target).toBeNull()
  })

  it('routes a link report to the admin queue despite having no group', () => {
    const target = notificationTarget(
      makeNotification({ type: 'link_report_submitted', group_id: null, album_id: 42 }),
    )
    expect(target).toBe('/admin?tab=reports')
  })
})
