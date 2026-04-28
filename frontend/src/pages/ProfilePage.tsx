import { useEffect, useState } from 'react'
import {
  Button,
  Divider,
  Group,
  PasswordInput,
  Skeleton,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { useQueryClient } from '@tanstack/react-query'
import { IconBrandSpotify } from '@tabler/icons-react'
import AppShell from '../components/layout/AppShell'
import StatsGrid from '../components/profile/StatsGrid'
import GroupStatsList from '../components/profile/GroupStatsList'
import MyNominationsPool from '../components/profile/MyNominationsPool'
import { useAuth } from '../hooks/useAuth'
import { useMyStats } from '../hooks/useStats'
import { useMyGroups } from '../hooks/useGroups'
import { apiFetch, ApiError } from '../services/apiClient'
import { getSpotifyConnectUrl, disconnectSpotify } from '../services/streamingService'

interface EditFormValues {
  username: string
  email: string
  password: string
}

export default function ProfilePage() {
  const { user, logout } = useAuth()
  const qc = useQueryClient()
  const { data: stats, isLoading: statsLoading } = useMyStats()
  const { data: groups } = useMyGroups(user?.username ?? '')
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [connectingSpotify, setConnectingSpotify] = useState(false)
  const [disconnectingSpotify, setDisconnectingSpotify] = useState(false)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const spotify = params.get('spotify')
    if (spotify === 'connected') {
      notifications.show({ color: 'green', message: 'Spotify connected successfully' })
      qc.invalidateQueries({ queryKey: ['stats', 'me'] })
    } else if (spotify === 'error') {
      notifications.show({ color: 'red', message: 'Could not connect Spotify — please try again' })
    }
    if (spotify) {
      const clean = new URL(window.location.href)
      clean.searchParams.delete('spotify')
      window.history.replaceState({}, '', clean.toString())
    }
  }, [])

  const handleSpotifyConnect = async () => {
    setConnectingSpotify(true)
    try {
      const url = await getSpotifyConnectUrl()
      window.location.href = url
    } catch {
      notifications.show({ color: 'red', message: 'Could not initiate Spotify connection' })
      setConnectingSpotify(false)
    }
  }

  const handleSpotifyDisconnect = async () => {
    setDisconnectingSpotify(true)
    try {
      await disconnectSpotify()
      await qc.invalidateQueries({ queryKey: ['stats', 'me'] })
      notifications.show({ color: 'green', message: 'Spotify disconnected' })
    } catch {
      notifications.show({ color: 'red', message: 'Could not disconnect Spotify' })
    } finally {
      setDisconnectingSpotify(false)
    }
  }

  const form = useForm<EditFormValues>({
    initialValues: {
      username: user?.username ?? '',
      email: user?.email ?? '',
      password: '',
    },
    validate: {
      username: (v) => {
        if (!v.trim()) return 'Required'
        if (v.length < 3 || v.length > 50) return '3–50 characters'
        if (!/^[A-Za-z0-9_-]+$/.test(v)) return 'Only letters, numbers, - and _'
        return null
      },
      email: (v) => (/^\S+@\S+\.\S+$/.test(v) ? null : 'Valid email required'),
    },
  })

  const handleSave = async (values: EditFormValues) => {
    setSaving(true)
    try {
      const payload: Record<string, string> = {}
      if (values.username !== user?.username) payload.username = values.username.toLowerCase()
      if (values.email !== user?.email) payload.email = values.email.toLowerCase()
      if (values.password) payload.password = values.password

      if (Object.keys(payload).length === 0) {
        setEditing(false)
        return
      }

      await apiFetch('/users/me', { method: 'PUT', body: JSON.stringify(payload) })
      await qc.invalidateQueries({ queryKey: ['stats', 'me'] })
      await qc.invalidateQueries({ queryKey: ['groups', 'mine'] })
      notifications.show({ color: 'green', message: 'Profile updated' })
      setEditing(false)

      // If username changed, re-login is required as the token references the old state.
      // Simple approach: log out and redirect.
      if (payload.username || payload.password) {
        notifications.show({ message: 'Please sign in again with your new credentials' })
        logout()
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Update failed'
      notifications.show({ color: 'red', message })
    } finally {
      setSaving(false)
    }
  }

  const joinedDate = user?.created_at
    ? new Date(user.created_at).toLocaleDateString()
    : '—'

  return (
    <AppShell>
      <Stack gap="xl" maw={560}>
        <div>
          <Title order={3} mb="xs">Profile</Title>
          <Text size="sm" c="dimmed">Member since {joinedDate}</Text>
        </div>

        {editing ? (
          <form onSubmit={form.onSubmit(handleSave)}>
            <Stack gap="md">
              <TextInput label="Username" {...form.getInputProps('username')} />
              <TextInput label="Email" {...form.getInputProps('email')} />
              <PasswordInput
                label="New password"
                description="Leave blank to keep current password"
                {...form.getInputProps('password')}
              />
              <Group gap="xs">
                <Button type="submit" loading={saving} size="sm">Save</Button>
                <Button variant="subtle" size="sm" onClick={() => setEditing(false)}>Cancel</Button>
              </Group>
            </Stack>
          </form>
        ) : (
          <Stack gap="xs">
            <Group justify="space-between">
              <div>
                <Text fw={500}>{user?.username}</Text>
                <Text size="sm" c="dimmed">{user?.email}</Text>
              </div>
              <Button size="xs" variant="light" onClick={() => setEditing(true)}>Edit</Button>
            </Group>
          </Stack>
        )}

        <Divider />

        <div>
          <Title order={5} mb="md">Connected services</Title>
          <Group justify="space-between">
            <Group gap="sm">
              <IconBrandSpotify size={20} color="#1DB954" />
              <div>
                <Text size="sm" fw={500}>Spotify</Text>
                <Text size="xs" c="dimmed">
                  {stats?.has_spotify ? 'Connected' : 'Not connected'}
                </Text>
              </div>
            </Group>
            {statsLoading ? (
              <Skeleton w={80} h={28} radius="sm" />
            ) : stats?.has_spotify ? (
              <Button
                size="xs"
                variant="subtle"
                color="red"
                loading={disconnectingSpotify}
                onClick={handleSpotifyDisconnect}
              >
                Disconnect
              </Button>
            ) : (
              <Button
                size="xs"
                variant="light"
                loading={connectingSpotify}
                onClick={handleSpotifyConnect}
              >
                Connect
              </Button>
            )}
          </Group>
        </div>

        <Divider />

        <div>
          <Title order={5} mb="md">All-time stats</Title>
          {statsLoading
            ? <Skeleton h={80} />
            : <StatsGrid stats={stats} isLoading={false} />
          }
        </div>

        <Divider />

        <div>
          <Title order={5} mb="md">Guess accuracy by group</Title>
          <GroupStatsList groups={groups ?? []} />
        </div>

        <Divider />

        <div>
          <Title order={5} mb="md">My nominations pool</Title>
          <MyNominationsPool />
        </div>
      </Stack>
    </AppShell>
  )
}
