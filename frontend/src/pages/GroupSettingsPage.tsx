import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ActionIcon,
  Button,
  Divider,
  Group,
  Modal,
  NumberInput,
  Select,
  Skeleton,
  Stack,
  Switch,
  Text,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconArrowLeft, IconUserMinus } from '@tabler/icons-react'
import AppShell from '../components/layout/AppShell'
import {
  useDeleteGroup,
  useGroup,
  useGroupMembers,
  useRemoveMember,
  useUpdateGroup,
  useUpdateMemberRole,
} from '../hooks/useGroups'
import { useAuth } from '../hooks/useAuth'
import { ApiError } from '../services/apiClient'
import { GroupMemberResponse } from '../types/group'

const ROLE_OPTIONS = [
  { value: 'member', label: 'Member' },
  { value: 'admin', label: 'Admin' },
  { value: 'owner', label: 'Owner' },
]

export default function GroupSettingsPage() {
  const { groupId } = useParams<{ groupId: string }>()
  const gid = Number(groupId)
  const navigate = useNavigate()

  const { user } = useAuth()
  const { data: group, isLoading: groupLoading } = useGroup(gid)
  const { data: members = [], isLoading: membersLoading } = useGroupMembers(gid)
  const updateGroup = useUpdateGroup(gid)
  const updateRole = useUpdateMemberRole(gid)
  const deleteGroup = useDeleteGroup()
  const removeMember = useRemoveMember()

  const [name, setName] = useState<string | null>(null)
  const [isPublic, setIsPublic] = useState<boolean | null>(null)
  const [minRoleToAddMembers, setMinRoleToAddMembers] = useState<string | null>(null)
  const [dailyAlbumCount, setDailyAlbumCount] = useState<number | string | null>(null)
  const [guessUserCap, setGuessUserCap] = useState<number | string | null>(null)
  const [chaosMode, setChaosMode] = useState<boolean | null>(null)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [memberToRemove, setMemberToRemove] = useState<GroupMemberResponse | null>(null)

  const currentName = name ?? group?.name ?? ''
  const currentPublic = isPublic ?? group?.is_public ?? true
  const currentMinRole = minRoleToAddMembers ?? group?.settings?.min_role_to_add_members ?? 'admin'
  const currentDailyCount = dailyAlbumCount ?? group?.settings?.daily_album_count ?? 1
  const currentGuessUserCap = guessUserCap ?? group?.settings?.guess_user_cap ?? 5
  const currentChaosMode = chaosMode ?? group?.settings?.chaos_mode ?? false

  const isOwner = group?.current_user_role === 'owner'
  const currentRole = group?.current_user_role

  const handleSave = async () => {
    try {
      await updateGroup.mutateAsync({
        name: currentName,
        is_public: currentPublic,
        settings: {
          min_role_to_add_members: currentMinRole,
          daily_album_count: typeof currentDailyCount === 'number' ? currentDailyCount : undefined,
          guess_user_cap: typeof currentGuessUserCap === 'number' ? currentGuessUserCap : undefined,
          chaos_mode: currentChaosMode,
        },
      })
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

  const canRemove = (target: GroupMemberResponse) => {
    if (target.user_id === user?.id) return false
    if (currentRole === 'owner') return true
    if (currentRole === 'admin') return target.role !== 'owner'
    return false
  }

  const handleRemoveMember = async () => {
    if (!memberToRemove) return
    try {
      await removeMember.mutateAsync({ groupId: gid, userId: memberToRemove.user_id })
      notifications.show({ color: 'green', message: `${memberToRemove.username} was removed` })
      setMemberToRemove(null)
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not remove member'
      notifications.show({ color: 'red', message })
      setMemberToRemove(null)
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
          <Title order={5}>Access & Policy</Title>
          <Select
            label="Who can add members"
            description="Minimum role required to add new members to this group."
            data={ROLE_OPTIONS}
            value={currentMinRole}
            onChange={(val) => val && setMinRoleToAddMembers(val)}
            allowDeselect={false}
            w={200}
          />
          <NumberInput
            label="Albums per day"
            description="Number of albums drawn for daily review (max 10)."
            value={currentDailyCount}
            onChange={setDailyAlbumCount}
            min={1}
            max={10}
            w={120}
          />
          <NumberInput
            label="Guess options shown"
            description="How many members appear as candidates when guessing the nominator (3–10)."
            value={currentGuessUserCap}
            onChange={setGuessUserCap}
            min={3}
            max={10}
            w={120}
          />
          <Switch
            label="Chaos mode"
            description="Each daily spin has a small chance of pulling a random album from outside the group's nominations."
            checked={currentChaosMode}
            onChange={(e) => setChaosMode(e.currentTarget.checked)}
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
                  <Group gap="xs">
                    <Select
                      size="xs"
                      w={110}
                      data={ROLE_OPTIONS}
                      value={m.role}
                      onChange={(val) => val && handleRoleChange(m.user_id, val)}
                      disabled={!isOwner && m.role === 'owner'}
                      allowDeselect={false}
                    />
                    <Tooltip label="Remove member" disabled={!canRemove(m)}>
                      <ActionIcon
                        variant="subtle"
                        color="red"
                        size="sm"
                        onClick={() => canRemove(m) && setMemberToRemove(m)}
                        style={{ visibility: canRemove(m) ? 'visible' : 'hidden' }}
                      >
                        <IconUserMinus size={14} />
                      </ActionIcon>
                    </Tooltip>
                  </Group>
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

      <Modal
        opened={memberToRemove !== null}
        onClose={() => setMemberToRemove(null)}
        title="Remove member"
      >
        <Text size="sm" mb="lg">
          Are you sure you want to remove <strong>{memberToRemove?.username}</strong> from this
          group?
        </Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={() => setMemberToRemove(null)}>
            Cancel
          </Button>
          <Button color="red" loading={removeMember.isPending} onClick={handleRemoveMember}>
            Remove
          </Button>
        </Group>
      </Modal>
    </AppShell>
  )
}
