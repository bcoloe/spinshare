import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { groupService } from '../services/groupService'
import { invitationService } from '../services/invitationService'
import { inviteLinkService } from '../services/inviteLinkService'
import type { GroupCreate, GroupModify } from '../types/group'

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

export function useAddMember(groupId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (userId: number) => groupService.addMember(groupId, userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['groups', groupId, 'members'] }),
  })
}

export function useUpdateMemberRole(groupId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: string }) =>
      groupService.updateMemberRole(groupId, userId, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['groups', groupId, 'members'] }),
  })
}

export function useUpdateGroup(groupId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: GroupModify) => groupService.update(groupId, data),
    onSuccess: (updated) => {
      qc.setQueryData(['groups', groupId], updated)
      qc.invalidateQueries({ queryKey: ['groups', 'mine'] })
    },
  })
}

export function useDeleteGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (groupId: number) => groupService.delete(groupId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['groups', 'mine'] }),
  })
}

export function useSendInvitation(groupId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (email: string) => invitationService.send(groupId, email),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['groups', groupId, 'invitations'] }),
  })
}

export function useInvitation(token: string) {
  return useQuery({
    queryKey: ['invitations', token],
    queryFn: () => invitationService.getByToken(token),
    enabled: !!token,
    retry: false,
  })
}

export function useMyPendingInvitations() {
  return useQuery({
    queryKey: ['invitations', 'pending'],
    queryFn: () => invitationService.getMyPending(),
    refetchInterval: 60_000,
  })
}

export function useAcceptInvitation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (token: string) => invitationService.accept(token),
    onSuccess: (inv) => {
      qc.invalidateQueries({ queryKey: ['invitations', 'pending'] })
      qc.invalidateQueries({ queryKey: ['groups', inv.group_id, 'members'] })
      qc.invalidateQueries({ queryKey: ['groups', 'mine'] })
    },
  })
}

export function useDeclineInvitation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (token: string) => invitationService.decline(token),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['invitations', 'pending'] }),
  })
}

export function useGroupPendingInvitations(groupId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['groups', groupId, 'invitations'],
    queryFn: () => invitationService.list(groupId),
    enabled: enabled && !!groupId,
  })
}

export function useGroupInviteLink(groupId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['groups', groupId, 'invite-link'],
    queryFn: () => inviteLinkService.get(groupId),
    enabled: enabled && !!groupId,
    retry: false,
  })
}

export function useCreateOrRotateInviteLink(groupId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => inviteLinkService.createOrRotate(groupId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['groups', groupId, 'invite-link'] }),
  })
}

export function useRevokeInviteLink(groupId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => inviteLinkService.revoke(groupId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['groups', groupId, 'invite-link'] }),
  })
}

export function useInviteLink(token: string) {
  return useQuery({
    queryKey: ['invite-links', token],
    queryFn: () => inviteLinkService.getByToken(token),
    enabled: !!token,
    retry: false,
  })
}

export function useAcceptInviteLink() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (token: string) => inviteLinkService.accept(token),
    onSuccess: (link) => {
      qc.invalidateQueries({ queryKey: ['groups', link.group_id, 'members'] })
      qc.invalidateQueries({ queryKey: ['groups', 'mine'] })
    },
  })
}
