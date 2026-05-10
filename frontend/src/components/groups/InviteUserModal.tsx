import { useState } from 'react'
import {
  ActionIcon,
  Button,
  CopyButton,
  Divider,
  Group,
  Loader,
  Modal,
  Stack,
  Text,
  TextInput,
  Tooltip,
} from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { IconCheck, IconCopy, IconRefresh, IconTrash } from '@tabler/icons-react'
import { useQuery } from '@tanstack/react-query'
import { userService } from '../../services/userService'
import {
  useGroupMembers,
  useGroupInviteLink,
  useCreateOrRotateInviteLink,
  useRevokeInviteLink,
  useSendInvitation,
} from '../../hooks/useGroups'
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
  const { data: inviteLink, isLoading: linkLoading } = useGroupInviteLink(groupId, opened)
  const createOrRotate = useCreateOrRotateInviteLink(groupId)
  const revokeLink = useRevokeInviteLink(groupId)

  const { data: results = [], isFetching } = useQuery({
    queryKey: ['users', 'search', debounced],
    queryFn: () => userService.search(debounced),
    enabled: debounced.length >= 2,
  })

  const memberIds = new Set(members.map((m) => m.user_id))
  const searched = debounced.length >= 2
  const noResults = searched && !isFetching && results.length === 0
  const looksLikeEmail = EMAIL_RE.test(debounced)

  const joinUrl = inviteLink
    ? `${window.location.origin}/join/${inviteLink.token}`
    : null

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

  const handleGenerateLink = async () => {
    try {
      await createOrRotate.mutateAsync()
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not generate link'
      notifications.show({ color: 'red', message })
    }
  }

  const handleRevokeLink = async () => {
    try {
      await revokeLink.mutateAsync()
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not revoke link'
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
        <Stack gap="xs">
          <Text size="sm" fw={500}>Shareable link</Text>
          {linkLoading ? (
            <Loader size="xs" />
          ) : joinUrl ? (
            <Stack gap="xs">
              <Group gap="xs" wrap="nowrap">
                <TextInput
                  value={joinUrl}
                  readOnly
                  size="xs"
                  style={{ flex: 1 }}
                  styles={{ input: { fontFamily: 'monospace', fontSize: 11 } }}
                />
                <CopyButton value={joinUrl} timeout={2000}>
                  {({ copied, copy }) => (
                    <Tooltip label={copied ? 'Copied!' : 'Copy link'}>
                      <ActionIcon
                        variant="light"
                        color={copied ? 'teal' : 'gray'}
                        size="lg"
                        onClick={copy}
                      >
                        {copied ? <IconCheck size={14} /> : <IconCopy size={14} />}
                      </ActionIcon>
                    </Tooltip>
                  )}
                </CopyButton>
                <Tooltip label="Regenerate link">
                  <ActionIcon
                    variant="light"
                    size="lg"
                    loading={createOrRotate.isPending}
                    onClick={handleGenerateLink}
                  >
                    <IconRefresh size={14} />
                  </ActionIcon>
                </Tooltip>
                <Tooltip label="Revoke link">
                  <ActionIcon
                    variant="light"
                    color="red"
                    size="lg"
                    loading={revokeLink.isPending}
                    onClick={handleRevokeLink}
                  >
                    <IconTrash size={14} />
                  </ActionIcon>
                </Tooltip>
              </Group>
              <Text size="xs" c="dimmed">Anyone with this link can join the group.</Text>
            </Stack>
          ) : (
            <Button
              variant="light"
              size="xs"
              loading={createOrRotate.isPending}
              onClick={handleGenerateLink}
            >
              Generate invite link
            </Button>
          )}
        </Stack>

        <Divider label="or invite by email" labelPosition="center" />

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
