export interface GroupResponse {
  id: number
  name: string
  created_at: string
}

export interface GroupSettings {
  min_role_to_add_members: 'owner' | 'admin' | 'member'
  min_role_to_nominate: 'owner' | 'admin' | 'member'
  daily_album_count: number
  allow_guessing: boolean
  guess_user_cap: number
  chaos_mode: boolean
  daily_nomination_limit: number | null
  timezone: string
  selection_days: number[]
  catch_up_enabled: boolean
}

export interface GroupDetailResponse extends GroupResponse {
  is_public: boolean
  is_global: boolean
  is_bot_group: boolean
  member_count: number
  current_user_role: 'owner' | 'admin' | 'member' | null
  settings: GroupSettings | null
}

export interface GroupMemberResponse {
  user_id: number
  username: string
  role: 'owner' | 'admin' | 'member'
  joined_at: string
  first_name: string | null
  last_name: string | null
  name_is_public: boolean
}

export interface AlbumsPerMemberItem {
  username: string
  count: number
}

export interface GroupDecadeBreakdownItem {
  decade: string
  count: number
}

export interface GuessHistogramBucket {
  label: string
  count: number
}

export interface MemberGuessAccuracyItem {
  username: string
  total_guesses: number
  correct_guesses: number
  accuracy: number
}

export interface GroupStatsResponse {
  member_count: number
  albums_added: number
  albums_reviewed: number
  formed_at: string
  albums_per_member: AlbumsPerMemberItem[]
  selected_per_member: AlbumsPerMemberItem[]
  decade_breakdown: GroupDecadeBreakdownItem[]
  guess_histogram: GuessHistogramBucket[]
  member_guess_accuracy: MemberGuessAccuracyItem[]
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
    min_role_to_nominate?: string
    daily_album_count?: number
    allow_guessing?: boolean
    guess_user_cap?: number
    chaos_mode?: boolean
    daily_nomination_limit?: number | null
    timezone?: string
    selection_days?: number[]
    catch_up_enabled?: boolean
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

export interface InviteLinkResponse {
  id: number
  group_id: number
  group_name: string
  created_by: number
  creator_username: string
  token: string
  created_at: string
}
