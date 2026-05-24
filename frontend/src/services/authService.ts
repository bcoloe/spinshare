import { apiFetch } from './apiClient'
import type { LoginRequest, LoginResponse, RegisterRequest, UserResponse } from '../types/auth'

export const authService = {
  login(credentials: LoginRequest): Promise<LoginResponse> {
    return apiFetch('/users/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    })
  },

  register(data: RegisterRequest): Promise<UserResponse> {
    return apiFetch('/users/register', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  refresh(refreshToken: string): Promise<LoginResponse> {
    return apiFetch(`/users/refresh?refresh_token=${encodeURIComponent(refreshToken)}`, {
      method: 'POST',
    })
  },

  getMe(): Promise<UserResponse> {
    return apiFetch('/users/me')
  },

  requestPasswordReset(email: string): Promise<void> {
    return apiFetch('/users/password-reset/request', {
      method: 'POST',
      body: JSON.stringify({ email }),
    })
  },

  confirmPasswordReset(token: string, newPassword: string): Promise<void> {
    return apiFetch('/users/password-reset/confirm', {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword }),
    })
  },
}
