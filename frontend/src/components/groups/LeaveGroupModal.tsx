import { Button, Group, Modal, Text } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useRemoveMember } from '../../hooks/useGroups'
import { ApiError } from '../../services/apiClient'

interface Props {
  groupId: number
  groupName: string
  opened: boolean
  onClose: () => void
}

export default function LeaveGroupModal({ groupId, groupName, opened, onClose }: Props) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const removeMember = useRemoveMember()

  const handleLeave = async () => {
    if (!user) return
    try {
      await removeMember.mutateAsync({ groupId, userId: user.id })
      notifications.show({ color: 'green', message: `You left ${groupName}` })
      navigate('/')
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not leave group'
      notifications.show({ color: 'red', message })
      onClose()
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title="Leave group">
      <Text size="sm" mb="lg">
        Are you sure you want to leave <strong>{groupName}</strong>? You will need to be
        re-invited to rejoin if the group is private.
      </Text>
      <Group justify="flex-end">
        <Button variant="default" onClick={onClose}>
          Cancel
        </Button>
        <Button color="red" loading={removeMember.isPending} onClick={handleLeave}>
          Leave
        </Button>
      </Group>
    </Modal>
  )
}
