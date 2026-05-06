import { useState } from 'react'
import { Button, Loader, Modal, Radio, Stack, Text } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useMyGroups } from '../../hooks/useGroups'
import { useSendInvitation } from '../../hooks/useGroups'
import { useAuth } from '../../hooks/useAuth'
import { ApiError } from '../../services/apiClient'
import type { GroupDetailResponse } from '../../types/group'

interface Props {
  targetEmail: string
  targetUsername: string
  opened: boolean
  onClose: () => void
}

export default function InviteToGroupModal({ targetEmail, targetUsername, opened, onClose }: Props) {
  const { user } = useAuth()
  const { data: groups = [], isLoading } = useMyGroups(user?.username ?? '')
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null)

  const selectedId = selectedGroupId ? parseInt(selectedGroupId) : null
  const sendInvitation = useSendInvitation(selectedId ?? 0)

  const handleClose = () => {
    setSelectedGroupId(null)
    onClose()
  }

  const handleInvite = async () => {
    if (!selectedId) return
    try {
      await sendInvitation.mutateAsync(targetEmail)
      notifications.show({ color: 'green', message: `Invitation sent to ${targetUsername}` })
      handleClose()
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not send invitation'
      notifications.show({ color: 'red', message })
    }
  }

  const invitableGroups = groups.filter(
    (g): g is GroupDetailResponse =>
      !g.is_global &&
      (g.current_user_role === 'owner' ||
        g.current_user_role === 'admin' ||
        g.settings?.min_role_to_add_members === 'member'),
  )

  return (
    <Modal opened={opened} onClose={handleClose} title={`Invite ${targetUsername} to a group`}>
      <Stack gap="md">
        {isLoading ? (
          <Loader size="sm" />
        ) : invitableGroups.length === 0 ? (
          <Text size="sm" c="dimmed">You don't have any groups you can invite members to.</Text>
        ) : (
          <Radio.Group value={selectedGroupId ?? ''} onChange={setSelectedGroupId}>
            <Stack gap="xs">
              {invitableGroups.map((g) => (
                <Radio key={g.id} value={String(g.id)} label={g.name} />
              ))}
            </Stack>
          </Radio.Group>
        )}

        <Button
          disabled={!selectedId || invitableGroups.length === 0}
          loading={sendInvitation.isPending}
          onClick={handleInvite}
        >
          Send invitation
        </Button>
      </Stack>
    </Modal>
  )
}
