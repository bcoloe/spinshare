import { useState } from 'react'
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
import AppShell from '../components/layout/AppShell'
import StatsGrid from '../components/profile/StatsGrid'
import GroupStatsList from '../components/profile/GroupStatsList'
import { useAuth } from '../hooks/useAuth'
import { useMyStats } from '../hooks/useStats'
import { useMyGroups } from '../hooks/useGroups'
import { apiFetch, ApiError } from '../services/apiClient'

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
      </Stack>
    </AppShell>
  )
}
