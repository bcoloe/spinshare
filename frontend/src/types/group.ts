export interface GroupResponse {
  id: number
  name: string
  created_at: string
}

export interface GroupSettings {
  min_role_to_add_members: 'owner' | 'admin' | 'member'
  daily_album_count: number
  allow_guessing: boolean
  guess_user_cap: number
}

export interface GroupDetailResponse extends GroupResponse {
  is_public: boolean
  is_global: boolean
  member_count: number
  current_user_role: 'owner' | 'admin' | 'member' | null
  settings: GroupSettings | null
}

export interface GroupMemberResponse {
  user_id: number
  username: string
  role: 'owner' | 'admin' | 'member'
  joined_at: string
}

export interface GroupStatsResponse {
  member_count: number
  albums_added: number
  albums_reviewed: number
  formed_at: string
}

export interface GroupCreate {
  name: string
  is_public: boolean
}

export interface GroupModify {
  name?: string
  is_public?: boolean
  settings?: {
    min_role_to_add_members?: string
    daily_album_count?: number
    guess_user_cap?: number
  }
}

export interface InvitationResponse {
  id: number
  group_id: number
  group_name: string
  invited_email: string
  invited_by: number
  inviter_username: string
  token: string
  created_at: string
  expires_at: string
  accepted_at: string | null
  status: 'pending' | 'accepted' | 'expired'
}
