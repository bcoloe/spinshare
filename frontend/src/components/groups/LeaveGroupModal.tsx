import { useState } from 'react'
import { Button, Group, Modal, Text, TextInput } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useRemoveMember } from '../../hooks/useGroups'
import { ApiError } from '../../services/apiClient'

interface Props {
  groupId: number
  groupName: string
  isLastMember?: boolean
  opened: boolean
  onClose: () => void
}

export default function LeaveGroupModal({
  groupId,
  groupName,
  isLastMember,
  opened,
  onClose,
}: Props) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const removeMember = useRemoveMember()
  const [confirmName, setConfirmName] = useState('')

  const handleClose = () => {
    setConfirmName('')
    onClose()
  }

  const handleLeave = async () => {
    if (!user) return
    try {
      await removeMember.mutateAsync({ groupId, userId: user.id })
      const message = isLastMember ? `${groupName} was deleted` : `You left ${groupName}`
      notifications.show({ color: 'green', message })
      navigate('/')
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not leave group'
      notifications.show({ color: 'red', message })
      handleClose()
    }
  }

  return (
    <Modal opened={opened} onClose={handleClose} title="Leave group">
      {isLastMember ? (
        <>
          <Text size="sm" mb="md">
            You are the last member of <strong>{groupName}</strong>. Leaving will permanently
            delete this group and all of its data. This action cannot be undone.
          </Text>
          <TextInput
            label={`Type "${groupName}" to confirm`}
            placeholder={groupName}
            value={confirmName}
            onChange={(e) => setConfirmName(e.currentTarget.value)}
            mb="lg"
          />
        </>
      ) : (
        <Text size="sm" mb="lg">
          Are you sure you want to leave <strong>{groupName}</strong>? You will need to be
          re-invited to rejoin if the group is private.
        </Text>
      )}
      <Group justify="flex-end">
        <Button variant="default" onClick={handleClose}>
          Cancel
        </Button>
        <Button
          color="red"
          loading={removeMember.isPending}
          disabled={isLastMember ? confirmName !== groupName : false}
          onClick={handleLeave}
        >
          {isLastMember ? 'Leave & delete group' : 'Leave'}
        </Button>
      </Group>
    </Modal>
  )
}
