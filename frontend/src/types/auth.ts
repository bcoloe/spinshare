export interface UserResponse {
  id: number
  email: string
  username: string
  created_at: string
}

export interface UserWithStats extends UserResponse {
  total_groups: number
  created_groups: number
  total_reviews: number
  albums_added: number
  has_spotify: boolean
}

export interface LoginRequest {
  email?: string
  username?: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: UserResponse
}

export interface RegisterRequest {
  email: string
  username: string
  password: string
}

export interface UserUpdate {
  email?: string
  username?: string
  password?: string
}
