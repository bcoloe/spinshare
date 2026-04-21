import { useState } from 'react'
import { Button, Group, Modal, Stack, Text, TextInput } from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useGroupSearch, useJoinGroup } from '../../hooks/useGroups'
import { ApiError } from '../../services/apiClient'

interface Props {
  opened: boolean
  onClose: () => void
}

export default function JoinGroupModal({ opened, onClose }: Props) {
  const [query, setQuery] = useState('')
  const [debouncedQuery] = useDebouncedValue(query, 300)
  const { data: results, isLoading } = useGroupSearch(debouncedQuery)
  const joinGroup = useJoinGroup()

  const handleJoin = async (groupId: number, name: string) => {
    try {
      await joinGroup.mutateAsync(groupId)
      notifications.show({ color: 'green', message: `Joined "${name}"` })
      onClose()
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not join group'
      notifications.show({ color: 'red', message })
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title="Find a group" centered>
      <Stack gap="md">
        <TextInput
          placeholder="Search by group name…"
          value={query}
          onChange={(e) => setQuery(e.currentTarget.value)}
          autoFocus
        />
        {isLoading && <Text size="sm" c="dimmed">Searching…</Text>}
        {results?.map((g) => (
          <Group key={g.id} justify="space-between">
            <div>
              <Text size="sm" fw={500}>{g.name}</Text>
              <Text size="xs" c="dimmed">{g.member_count} members</Text>
            </div>
            <Button
              size="xs"
              variant={g.current_user_role ? 'filled' : 'light'}
              color={g.current_user_role ? 'green' : 'violet'}
              disabled={!!g.current_user_role}
              loading={joinGroup.isPending}
              onClick={() => handleJoin(g.id, g.name)}
            >
              {g.current_user_role ? 'Joined' : 'Join'}
            </Button>
          </Group>
        ))}
        {results?.length === 0 && debouncedQuery.length >= 2 && (
          <Text size="sm" c="dimmed">No groups found</Text>
        )}
      </Stack>
    </Modal>
  )
}
