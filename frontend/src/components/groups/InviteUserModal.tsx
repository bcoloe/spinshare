import { useState } from 'react'
import { Button, Group, Loader, Modal, Stack, Text, TextInput } from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useQuery } from '@tanstack/react-query'
import { userService } from '../../services/userService'
import { useGroupMembers, useSendInvitation } from '../../hooks/useGroups'
import { ApiError } from '../../services/apiClient'
import type { UserResponse } from '../../types/auth'

interface Props {
  groupId: number
  opened: boolean
  onClose: () => void
}

const EMAIL_RE = /^\S+@\S+\.\S+$/

export default function InviteUserModal({ groupId, opened, onClose }: Props) {
  const [query, setQuery] = useState('')
  const [debounced] = useDebouncedValue(query, 300)
  const sendInvitation = useSendInvitation(groupId)
  const { data: members = [] } = useGroupMembers(groupId)

  const { data: results = [], isFetching } = useQuery({
    queryKey: ['users', 'search', debounced],
    queryFn: () => userService.search(debounced),
    enabled: debounced.length >= 2,
  })

  const memberIds = new Set(members.map((m) => m.user_id))
  const searched = debounced.length >= 2
  const noResults = searched && !isFetching && results.length === 0
  const looksLikeEmail = EMAIL_RE.test(debounced)

  const handleInviteUser = async (u: UserResponse) => {
    await handleSendInvite(u.email)
  }

  const handleSendInvite = async (email: string) => {
    try {
      await sendInvitation.mutateAsync(email)
      notifications.show({ color: 'green', message: `Invitation sent to ${email}` })
      setQuery('')
      onClose()
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not send invitation'
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
          placeholder="Search by username or email..."
          value={query}
          onChange={(e) => setQuery(e.currentTarget.value)}
          rightSection={isFetching ? <Loader size="xs" /> : null}
        />

        {results.length > 0 && (
          <Stack gap="xs">
            {results.map((u) => (
              <Group key={u.id} justify="space-between">
                <Text size="sm">{u.username}</Text>
                {memberIds.has(u.id) ? (
                  <Text size="xs" c="dimmed">Already a member</Text>
                ) : (
                  <Button
                    size="xs"
                    variant="light"
                    loading={sendInvitation.isPending}
                    onClick={() => handleInviteUser(u)}
                  >
                    Invite
                  </Button>
                )}
              </Group>
            ))}
          </Stack>
        )}

        {noResults && (
          <Stack gap="xs">
            <Text size="sm" c="dimmed">No SpinShare account found.</Text>
            {looksLikeEmail && (
              <Button
                variant="light"
                loading={sendInvitation.isPending}
                onClick={() => handleSendInvite(debounced)}
              >
                Send invitation to {debounced}
              </Button>
            )}
          </Stack>
        )}
      </Stack>
    </Modal>
  )
}
