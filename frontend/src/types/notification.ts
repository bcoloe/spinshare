export type NotificationType =
  | 'invitation_accepted'
  | 'invitation_declined'
  | 'nomination_pool_low'
  | 'member_reviewed_album'
  | 'new_member_joined'

export interface NotificationResponse {
  id: number
  type: NotificationType
  message: string
  group_id: number | null
  read_at: string | null
  created_at: string
}
