import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Avatar,
  Button,
  Group,
  Loader,
  Modal,
  Stack,
  Text,
  TextInput,
  UnstyledButton,
} from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useQuery } from '@tanstack/react-query'
import { useGroupSearch, useJoinGroup } from '../../hooks/useGroups'
import { userService } from '../../services/userService'
import { ApiError } from '../../services/apiClient'

interface Props {
  opened: boolean
  onClose: () => void
}

const MAX_PREVIEW = 5

export default function SearchModal({ opened, onClose }: Props) {
  const [query, setQuery] = useState('')
  const [debounced] = useDebouncedValue(query, 300)
  const navigate = useNavigate()
  const joinGroup = useJoinGroup()

  const active = debounced.length >= 2

  const { data: groups = [], isFetching: groupsFetching } = useGroupSearch(debounced)
  const { data: users = [], isFetching: usersFetching } = useQuery({
    queryKey: ['users', 'search', debounced],
    queryFn: () => userService.search(debounced),
    enabled: active,
  })

  const isFetching = groupsFetching || usersFetching
  const hasResults = groups.length > 0 || users.length > 0

  const handleJoin = async (groupId: number, name: string) => {
    try {
      await joinGroup.mutateAsync(groupId)
      notifications.show({ color: 'green', message: `Joined "${name}"` })
      handleClose()
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not join group'
      notifications.show({ color: 'red', message })
    }
  }

  const handleUserClick = (username: string) => {
    navigate(`/users/${username}`)
    handleClose()
  }

  const handleBrowseAll = () => {
    navigate(`/search?q=${encodeURIComponent(debounced)}`)
    handleClose()
  }

  const handleClose = () => {
    setQuery('')
    onClose()
  }

  return (
    <Modal opened={opened} onClose={handleClose} title="Search" size="md">
      <Stack gap="sm">
        <TextInput
          placeholder="Search groups or users..."
          value={query}
          onChange={(e) => setQuery(e.currentTarget.value)}
          rightSection={isFetching ? <Loader size="xs" /> : null}
          autoFocus
        />

        {active && !isFetching && !hasResults && (
          <Text size="sm" c="dimmed">No results found.</Text>
        )}

        {groups.length > 0 && (
          <Stack gap="xs">
            <Text size="xs" fw={600} c="dimmed" tt="uppercase">Groups</Text>
            {groups.slice(0, MAX_PREVIEW).map((g) => (
              <Group key={g.id} justify="space-between">
                <div>
                  <Text size="sm" fw={500}>{g.name}</Text>
                  <Text size="xs" c="dimmed">{g.member_count} member{g.member_count !== 1 ? 's' : ''}</Text>
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
          </Stack>
        )}

        {users.length > 0 && (
          <Stack gap={4}>
            <Text size="xs" fw={600} c="dimmed" tt="uppercase">Users</Text>
            {users.slice(0, MAX_PREVIEW).map((u) => (
              <UnstyledButton
                key={u.id}
                onClick={() => handleUserClick(u.username)}
                style={{ borderRadius: 6, padding: '6px 8px' }}
              >
                <Group gap="sm">
                  <Avatar size="sm" radius="xl" color="violet">
                    {u.username[0].toUpperCase()}
                  </Avatar>
                  <Text size="sm">{u.username}</Text>
                </Group>
              </UnstyledButton>
            ))}
          </Stack>
        )}

        {active && (
          <Button
            variant="subtle"
            size="xs"
            onClick={handleBrowseAll}
            style={{ alignSelf: 'flex-start' }}
          >
            Browse all results{debounced ? ` for "${debounced}"` : ''}
          </Button>
        )}
      </Stack>
    </Modal>
  )
}
