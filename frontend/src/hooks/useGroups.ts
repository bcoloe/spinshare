import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { groupService } from '../services/groupService'
import type { GroupCreate } from '../types/group'

export function useMyGroups(username: string) {
  return useQuery({
    queryKey: ['groups', 'mine', username],
    queryFn: () => groupService.searchByUsername(username),
    enabled: !!username,
  })
}

export function useGroupSearch(query: string) {
  return useQuery({
    queryKey: ['groups', 'search', query],
    queryFn: () => groupService.search(query),
    enabled: query.length >= 2,
  })
}

export function useGroup(groupId: number) {
  return useQuery({
    queryKey: ['groups', groupId],
    queryFn: () => groupService.getById(groupId),
    enabled: !!groupId,
  })
}

export function useGroupMembers(groupId: number) {
  return useQuery({
    queryKey: ['groups', groupId, 'members'],
    queryFn: () => groupService.getMembers(groupId),
    enabled: !!groupId,
  })
}

export function useGroupStats(groupId: number) {
  return useQuery({
    queryKey: ['groups', groupId, 'stats'],
    queryFn: () => groupService.getStats(groupId),
    enabled: !!groupId,
  })
}

export function useCreateGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: GroupCreate) => groupService.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['groups', 'mine'] }),
  })
}

export function useJoinGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (groupId: number) => groupService.join(groupId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['groups', 'mine'] }),
  })
}

export function useRemoveMember() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ groupId, userId }: { groupId: number; userId: number }) =>
      groupService.removeMember(groupId, userId),
    onSuccess: (_data, { groupId }) =>
      qc.invalidateQueries({ queryKey: ['groups', groupId, 'members'] }),
  })
}
