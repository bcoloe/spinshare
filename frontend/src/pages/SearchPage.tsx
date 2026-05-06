import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Avatar,
  Button,
  Group,
  Loader,
  Paper,
  SegmentedControl,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useQuery } from '@tanstack/react-query'
import AppShell from '../components/layout/AppShell'
import { useGroupSearch, useJoinGroup } from '../hooks/useGroups'
import { userService } from '../services/userService'
import { ApiError } from '../services/apiClient'

type Tab = 'all' | 'groups' | 'users'

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const [query, setQuery] = useState(searchParams.get('q') ?? '')
  const [debounced] = useDebouncedValue(query, 300)
  const [tab, setTab] = useState<Tab>('all')
  const joinGroup = useJoinGroup()

  useEffect(() => {
    const q = searchParams.get('q') ?? ''
    if (q !== query) setQuery(q)
  }, [searchParams]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (debounced) {
      setSearchParams({ q: debounced }, { replace: true })
    } else {
      setSearchParams({}, { replace: true })
    }
  }, [debounced, setSearchParams])

  const active = debounced.length >= 2

  const { data: groups = [], isFetching: groupsFetching } = useGroupSearch(debounced)
  const { data: users = [], isFetching: usersFetching } = useQuery({
    queryKey: ['users', 'search', debounced],
    queryFn: () => userService.search(debounced),
    enabled: active,
  })

  const isFetching = groupsFetching || usersFetching
  const showGroups = tab === 'all' || tab === 'groups'
  const showUsers = tab === 'all' || tab === 'users'

  const handleJoin = async (groupId: number, name: string) => {
    try {
      await joinGroup.mutateAsync(groupId)
      notifications.show({ color: 'green', message: `Joined "${name}"` })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not join group'
      notifications.show({ color: 'red', message })
    }
  }

  return (
    <AppShell>
      <Stack gap="lg">
        <Title order={3}>Search</Title>

        <Stack gap="sm">
          <TextInput
            placeholder="Search groups or users..."
            value={query}
            onChange={(e) => setQuery(e.currentTarget.value)}
            rightSection={isFetching ? <Loader size="xs" /> : null}
            size="md"
            autoFocus
          />
          <SegmentedControl
            value={tab}
            onChange={(v) => setTab(v as Tab)}
            w="fit-content"
            data={[
              { label: 'All', value: 'all' },
              {
                label: active && groups.length > 0 ? `Groups (${groups.length})` : 'Groups',
                value: 'groups',
              },
              {
                label: active && users.length > 0 ? `Users (${users.length})` : 'Users',
                value: 'users',
              },
            ]}
          />
        </Stack>

        {!active && (
          <Text c="dimmed" size="sm">Enter at least 2 characters to search.</Text>
        )}

        {active && !isFetching && groups.length === 0 && users.length === 0 && (
          <Text c="dimmed" size="sm">No results found for "{debounced}".</Text>
        )}

        {showGroups && groups.length > 0 && (
          <Stack gap="xs">
            <Text size="sm" fw={600} c="dimmed" tt="uppercase">Groups</Text>
            {groups.map((g) => (
              <Paper key={g.id} withBorder p="sm" radius="md">
                <Group justify="space-between">
                  <div>
                    <Text fw={500}>{g.name}</Text>
                    <Text size="xs" c="dimmed">
                      {g.member_count} member{g.member_count !== 1 ? 's' : ''}
                    </Text>
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
              </Paper>
            ))}
          </Stack>
        )}

        {showUsers && users.length > 0 && (
          <Stack gap="xs">
            <Text size="sm" fw={600} c="dimmed" tt="uppercase">Users</Text>
            {users.map((u) => (
              <Paper
                key={u.id}
                withBorder
                p="sm"
                radius="md"
                style={{ cursor: 'pointer' }}
                onClick={() => navigate(`/users/${u.username}`)}
              >
                <Group gap="sm">
                  <Avatar size="md" radius="xl" color="violet">
                    {u.username[0].toUpperCase()}
                  </Avatar>
                  <Text fw={500}>{u.username}</Text>
                </Group>
              </Paper>
            ))}
          </Stack>
        )}
      </Stack>
    </AppShell>
  )
}
