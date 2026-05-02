import { ActionIcon, Avatar, Badge, Group, Skeleton, Stack, Text, UnstyledButton } from '@mantine/core'
import { IconUserMinus } from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import { useNavigate } from 'react-router-dom'
import { useGroupMembers, useRemoveMember } from '../../hooks/useGroups'
import { useAuth } from '../../hooks/useAuth'
import type { GroupDetailResponse } from '../../types/group'
import { ApiError } from '../../services/apiClient'

const ROLE_COLOR = { owner: 'violet', admin: 'blue', member: 'gray' } as const

interface Props {
  group: GroupDetailResponse
}

export default function MemberList({ group }: Props) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { data: members, isLoading } = useGroupMembers(group.id)
  const removeMember = useRemoveMember()

  const canManage = group.current_user_role === 'owner' || group.current_user_role === 'admin'

  const handleRemove = async (userId: number, username: string) => {
    try {
      await removeMember.mutateAsync({ groupId: group.id, userId })
      notifications.show({ color: 'green', message: `Removed ${username}` })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not remove member'
      notifications.show({ color: 'red', message })
    }
  }

  if (isLoading) {
    return (
      <Stack gap="xs">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} h={40} radius="sm" />)}
      </Stack>
    )
  }

  return (
    <Stack gap="xs">
      {members?.map((m) => (
        <Group key={m.user_id} justify="space-between">
          <UnstyledButton onClick={() => navigate(`/users/${m.username}`)}>
            <Group gap="sm">
              <Avatar size="sm" radius="xl" color="violet">
                {m.username[0].toUpperCase()}
              </Avatar>
              <Text size="sm">{m.username}</Text>
              <Badge size="xs" color={ROLE_COLOR[m.role]} variant="light">
                {m.role}
              </Badge>
            </Group>
          </UnstyledButton>
          {canManage && m.user_id !== user?.id && m.role !== 'owner' && (
            <ActionIcon
              size="sm"
              variant="subtle"
              color="red"
              onClick={() => handleRemove(m.user_id, m.username)}
              loading={removeMember.isPending}
            >
              <IconUserMinus size={14} />
            </ActionIcon>
          )}
        </Group>
      ))}
    </Stack>
  )
}
