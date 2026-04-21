import { useState } from 'react'
import { Button, Group, Loader, Modal, Stack, Text, TextInput } from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useQuery } from '@tanstack/react-query'
import { userService } from '../../services/userService'
import { useAddMember, useGroupMembers } from '../../hooks/useGroups'
import { ApiError } from '../../services/apiClient'
import type { UserResponse } from '../../types/auth'

interface Props {
  groupId: number
  opened: boolean
  onClose: () => void
}

export default function InviteUserModal({ groupId, opened, onClose }: Props) {
  const [query, setQuery] = useState('')
  const [debounced] = useDebouncedValue(query, 300)
  const addMember = useAddMember(groupId)
  const { data: members = [] } = useGroupMembers(groupId)

  const { data: results = [], isFetching } = useQuery({
    queryKey: ['users', 'search', debounced],
    queryFn: () => userService.search(debounced),
    enabled: debounced.length >= 2,
  })

  const memberIds = new Set(members.map((m) => m.user_id))

  const handleAdd = async (u: UserResponse) => {
    try {
      await addMember.mutateAsync(u.id)
      notifications.show({ color: 'green', message: `${u.username} added to group` })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not invite user'
      notifications.show({ color: 'red', message })
    }
  }

  const handleClose = () => {
    setQuery('')
    onClose()
  }

  return (
    <Modal opened={opened} onClose={handleClose} title="Invite member">
      <Stack gap="sm">
        <TextInput
          placeholder="Search by username..."
          value={query}
          onChange={(e) => setQuery(e.currentTarget.value)}
          rightSection={isFetching ? <Loader size="xs" /> : null}
        />
        {debounced.length >= 2 && results.length === 0 && !isFetching && (
          <Text size="sm" c="dimmed">
            No users found.
          </Text>
        )}
        <Stack gap="xs">
          {results.map((u) => (
            <Group key={u.id} justify="space-between">
              <Text size="sm">{u.username}</Text>
              {memberIds.has(u.id) ? (
                <Text size="xs" c="dimmed">
                  Already a member
                </Text>
              ) : (
                <Button
                  size="xs"
                  variant="light"
                  loading={addMember.isPending}
                  onClick={() => handleAdd(u)}
                >
                  Invite
                </Button>
              )}
            </Group>
          ))}
        </Stack>
      </Stack>
    </Modal>
  )
}
