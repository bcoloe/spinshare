import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Button,
  Divider,
  Group,
  Modal,
  Select,
  Skeleton,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconArrowLeft } from '@tabler/icons-react'
import AppShell from '../components/layout/AppShell'
import {
  useDeleteGroup,
  useGroup,
  useGroupMembers,
  useUpdateGroup,
  useUpdateMemberRole,
} from '../hooks/useGroups'
import { ApiError } from '../services/apiClient'

const ROLE_OPTIONS = [
  { value: 'member', label: 'Member' },
  { value: 'admin', label: 'Admin' },
  { value: 'owner', label: 'Owner' },
]

export default function GroupSettingsPage() {
  const { groupId } = useParams<{ groupId: string }>()
  const gid = Number(groupId)
  const navigate = useNavigate()

  const { data: group, isLoading: groupLoading } = useGroup(gid)
  const { data: members = [], isLoading: membersLoading } = useGroupMembers(gid)
  const updateGroup = useUpdateGroup(gid)
  const updateRole = useUpdateMemberRole(gid)
  const deleteGroup = useDeleteGroup()

  const [name, setName] = useState<string | null>(null)
  const [isPublic, setIsPublic] = useState<boolean | null>(null)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)

  const currentName = name ?? group?.name ?? ''
  const currentPublic = isPublic ?? group?.is_public ?? true

  const isOwner = group?.current_user_role === 'owner'

  const handleSave = async () => {
    try {
      await updateGroup.mutateAsync({ name: currentName, is_public: currentPublic })
      notifications.show({ color: 'green', message: 'Settings saved' })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not save settings'
      notifications.show({ color: 'red', message })
    }
  }

  const handleRoleChange = async (userId: number, role: string) => {
    try {
      await updateRole.mutateAsync({ userId, role })
      notifications.show({ color: 'green', message: 'Role updated' })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not update role'
      notifications.show({ color: 'red', message })
    }
  }

  const handleDelete = async () => {
    try {
      await deleteGroup.mutateAsync(gid)
      notifications.show({ color: 'green', message: 'Group deleted' })
      navigate('/')
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not delete group'
      notifications.show({ color: 'red', message })
      setDeleteConfirmOpen(false)
    }
  }

  if (groupLoading) {
    return (
      <AppShell>
        <Skeleton h={300} radius="md" />
      </AppShell>
    )
  }

  return (
    <AppShell>
      <Stack gap="xl" maw={600}>
        <Group gap="sm">
          <Button
            variant="subtle"
            leftSection={<IconArrowLeft size={16} />}
            onClick={() => navigate(`/groups/${gid}`)}
            px={0}
          >
            Back
          </Button>
          <Title order={3}>{group?.name} — Settings</Title>
        </Group>

        <Stack gap="md">
          <Title order={5}>General</Title>
          <TextInput
            label="Group name"
            value={currentName}
            onChange={(e) => setName(e.currentTarget.value)}
          />
          <Switch
            label="Public group"
            description="Public groups can be found and joined by anyone."
            checked={currentPublic}
            onChange={(e) => setIsPublic(e.currentTarget.checked)}
          />
          <Button
            style={{ alignSelf: 'flex-start' }}
            loading={updateGroup.isPending}
            onClick={handleSave}
          >
            Save
          </Button>
        </Stack>

        <Divider />

        <Stack gap="md">
          <Title order={5}>Members</Title>
          {membersLoading ? (
            <Stack gap="xs">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} h={36} radius="sm" />
              ))}
            </Stack>
          ) : (
            <Stack gap="sm">
              {members.map((m) => (
                <Group key={m.user_id} justify="space-between">
                  <Text size="sm">{m.username}</Text>
                  <Select
                    size="xs"
                    w={110}
                    data={ROLE_OPTIONS}
                    value={m.role}
                    onChange={(val) => val && handleRoleChange(m.user_id, val)}
                    disabled={!isOwner && m.role === 'owner'}
                    allowDeselect={false}
                  />
                </Group>
              ))}
            </Stack>
          )}
        </Stack>

        {isOwner && (
          <>
            <Divider />
            <Stack gap="md">
              <Title order={5} c="red">Danger zone</Title>
              <Text size="sm" c="dimmed">
                Permanently delete this group and all of its data. This cannot be undone.
              </Text>
              <Button
                color="red"
                variant="outline"
                style={{ alignSelf: 'flex-start' }}
                onClick={() => setDeleteConfirmOpen(true)}
              >
                Delete group
              </Button>
            </Stack>
          </>
        )}
      </Stack>

      <Modal
        opened={deleteConfirmOpen}
        onClose={() => setDeleteConfirmOpen(false)}
        title="Delete group"
      >
        <Text size="sm" mb="lg">
          Are you sure you want to permanently delete <strong>{group?.name}</strong>? This
          action cannot be undone.
        </Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={() => setDeleteConfirmOpen(false)}>
            Cancel
          </Button>
          <Button color="red" loading={deleteGroup.isPending} onClick={handleDelete}>
            Delete
          </Button>
        </Group>
      </Modal>
    </AppShell>
  )
}
