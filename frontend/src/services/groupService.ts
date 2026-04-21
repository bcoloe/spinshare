import { apiFetch } from './apiClient'
import type {
  GroupCreate,
  GroupDetailResponse,
  GroupMemberResponse,
  GroupModify,
  GroupResponse,
  GroupStatsResponse,
} from '../types/group'

export const groupService = {
  search(query: string): Promise<GroupDetailResponse[]> {
    return apiFetch(`/groups/search?query=${encodeURIComponent(query)}`)
  },

  searchByUsername(username: string): Promise<GroupDetailResponse[]> {
    return apiFetch(`/groups/search?username=${encodeURIComponent(username)}`)
  },

  getById(groupId: number): Promise<GroupDetailResponse> {
    return apiFetch(`/groups/${groupId}`)
  },

  create(data: GroupCreate): Promise<GroupResponse> {
    return apiFetch('/groups/', { method: 'POST', body: JSON.stringify(data) })
  },

  update(groupId: number, data: GroupModify): Promise<GroupDetailResponse> {
    return apiFetch(`/groups/${groupId}`, { method: 'PATCH', body: JSON.stringify(data) })
  },

  delete(groupId: number): Promise<void> {
    return apiFetch(`/groups/${groupId}`, { method: 'DELETE' })
  },

  join(groupId: number): Promise<{ joined_at: string }> {
    return apiFetch(`/groups/${groupId}/join`, { method: 'POST' })
  },

  getMembers(groupId: number): Promise<GroupMemberResponse[]> {
    return apiFetch(`/groups/${groupId}/members`)
  },

  removeMember(groupId: number, userId: number): Promise<void> {
    return apiFetch(`/groups/${groupId}/members/${userId}`, { method: 'DELETE' })
  },

  addMember(groupId: number, userId: number): Promise<void> {
    return apiFetch(`/groups/${groupId}/members`, {
      method: 'POST',
      body: JSON.stringify({ user_id: userId }),
    })
  },

  updateMemberRole(groupId: number, userId: number, role: string): Promise<GroupMemberResponse> {
    return apiFetch(`/groups/${groupId}/members/${userId}/role`, {
      method: 'PUT',
      body: JSON.stringify({ role }),
    })
  },

  getStats(groupId: number): Promise<GroupStatsResponse> {
    return apiFetch(`/groups/${groupId}/stats`)
  },
}
