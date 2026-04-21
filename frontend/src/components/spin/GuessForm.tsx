import { useState } from 'react'
import { Button, Radio, Stack, Text } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useCheckGuess } from '../../hooks/useDailySpin'
import { useGroupMembers } from '../../hooks/useGroups'
import { useAuth } from '../../hooks/useAuth'
import { ApiError } from '../../services/apiClient'

interface Props {
  groupId: number
  groupAlbumId: number
}

export default function GuessForm({ groupId, groupAlbumId }: Props) {
  const { user } = useAuth()
  const { data: members } = useGroupMembers(groupId)
  const checkGuess = useCheckGuess(groupId, groupAlbumId)
  const [selected, setSelected] = useState<string>('')

  const eligibleMembers = members?.filter((m) => m.user_id !== user?.id) ?? []

  const handleSubmit = async () => {
    if (!selected) {
      notifications.show({ color: 'red', message: 'Select a member' })
      return
    }
    try {
      await checkGuess.mutateAsync({ guessed_user_id: Number(selected) })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not submit guess'
      notifications.show({ color: 'red', message })
    }
  }

  return (
    <Stack gap="md">
      <Text size="sm" fw={600}>Who nominated this album?</Text>
      <Radio.Group value={selected} onChange={setSelected}>
        <Stack gap="xs">
          {eligibleMembers.map((m) => (
            <Radio key={m.user_id} value={String(m.user_id)} label={m.username} />
          ))}
        </Stack>
      </Radio.Group>
      <Button
        onClick={handleSubmit}
        loading={checkGuess.isPending}
        disabled={!selected}
        variant="light"
      >
        Submit guess
      </Button>
    </Stack>
  )
}
