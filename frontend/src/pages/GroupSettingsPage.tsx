import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ActionIcon,
  Button,
  Chip,
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

const TIMEZONE_OPTIONS = [
  { value: 'America/New_York', label: 'Eastern (ET)' },
  { value: 'America/Chicago', label: 'Central (CT)' },
  { value: 'America/Denver', label: 'Mountain (MT)' },
  { value: 'America/Los_Angeles', label: 'Pacific (PT)' },
  { value: 'America/Anchorage', label: 'Alaska (AKT)' },
  { value: 'Pacific/Honolulu', label: 'Hawaii (HT)' },
  { value: 'America/Toronto', label: 'Toronto (ET)' },
  { value: 'America/Vancouver', label: 'Vancouver (PT)' },
  { value: 'Europe/London', label: 'London (GMT/BST)' },
  { value: 'Europe/Paris', label: 'Paris (CET)' },
  { value: 'Europe/Berlin', label: 'Berlin (CET)' },
  { value: 'Europe/Helsinki', label: 'Helsinki (EET)' },
  { value: 'Asia/Dubai', label: 'Dubai (GST)' },
  { value: 'Asia/Kolkata', label: 'India (IST)' },
  { value: 'Asia/Bangkok', label: 'Bangkok (ICT)' },
  { value: 'Asia/Singapore', label: 'Singapore (SGT)' },
  { value: 'Asia/Tokyo', label: 'Tokyo (JST)' },
  { value: 'Asia/Seoul', label: 'Seoul (KST)' },
  { value: 'Australia/Sydney', label: 'Sydney (AEST)' },
  { value: 'Pacific/Auckland', label: 'Auckland (NZST)' },
  { value: 'UTC', label: 'UTC' },
]

const DAY_OPTIONS = [
  { value: '0', label: 'Mon' },
  { value: '1', label: 'Tue' },
  { value: '2', label: 'Wed' },
  { value: '3', label: 'Thu' },
  { value: '4', label: 'Fri' },
  { value: '5', label: 'Sat' },
  { value: '6', label: 'Sun' },
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
  const [minRoleToNominate, setMinRoleToNominate] = useState<string | null>(null)
  const [dailyAlbumCount, setDailyAlbumCount] = useState<number | string | null>(null)
  const [allowGuessing, setAllowGuessing] = useState<boolean | null>(null)
  const [guessUserCap, setGuessUserCap] = useState<number | string | null>(null)
  const [chaosMode, setChaosMode] = useState<boolean | null>(null)
  const [catchUpEnabled, setCatchUpEnabled] = useState<boolean | null>(null)
  const [dealerMode, setDealerMode] = useState<boolean | null>(null)
  const [dealerRollsPerDay, setDealerRollsPerDay] = useState<number | string | null>(null)
  const [dailyNominationLimit, setDailyNominationLimit] = useState<number | string | null | undefined>(undefined)
  const [timezone, setTimezone] = useState<string | null>(null)
  const [selectionDays, setSelectionDays] = useState<number[] | null>(null)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [memberToRemove, setMemberToRemove] = useState<GroupMemberResponse | null>(null)

  const currentName = name ?? group?.name ?? ''
  const currentPublic = isPublic ?? group?.is_public ?? true
  const currentMinRole = minRoleToAddMembers ?? group?.settings?.min_role_to_add_members ?? 'admin'
  const currentMinRoleToNominate = minRoleToNominate ?? group?.settings?.min_role_to_nominate ?? 'member'
  const currentDailyCount = dailyAlbumCount ?? group?.settings?.daily_album_count ?? 1
  const currentAllowGuessing = allowGuessing ?? group?.settings?.allow_guessing ?? true
  const currentGuessUserCap = guessUserCap ?? group?.settings?.guess_user_cap ?? 5
  const currentChaosMode = chaosMode ?? group?.settings?.chaos_mode ?? false
  const currentCatchUpEnabled = catchUpEnabled ?? group?.settings?.catch_up_enabled ?? false
  const currentDealerMode = dealerMode ?? group?.settings?.dealer_mode ?? false
  const currentDealerRollsPerDay = dealerRollsPerDay ?? group?.settings?.dealer_rolls_per_day ?? 1
  const currentDailyNominationLimit: string | number = (() => {
    const raw = dailyNominationLimit === undefined
      ? group?.settings?.daily_nomination_limit
      : dailyNominationLimit
    if (raw === null || raw === undefined || raw === '') return ''
    return raw as number
  })()
  const currentTimezone = timezone ?? group?.settings?.timezone ?? 'America/New_York'
  const currentSelectionDays = selectionDays ?? group?.settings?.selection_days ?? [0,1,2,3,4,5,6]

  const isOwner = group?.current_user_role === 'owner'
  const currentRole = group?.current_user_role

  const handleSaveGlobalDealer = async () => {
    try {
      await updateGroup.mutateAsync({
        settings: {
          dealer_mode: currentDealerMode,
          dealer_rolls_per_day:
            typeof currentDealerRollsPerDay === 'number' ? currentDealerRollsPerDay : undefined,
        },
      })
      notifications.show({ color: 'green', message: 'Dealer mode updated' })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not save settings'
      notifications.show({ color: 'red', message })
    }
  }

  const handleSave = async () => {
    try {
      await updateGroup.mutateAsync({
        name: currentName,
        is_public: currentPublic,
        settings: {
          min_role_to_add_members: currentMinRole,
          min_role_to_nominate: currentMinRoleToNominate,
          daily_album_count: typeof currentDailyCount === 'number' ? currentDailyCount : undefined,
          allow_guessing: currentAllowGuessing,
          guess_user_cap: typeof currentGuessUserCap === 'number' ? currentGuessUserCap : undefined,
          chaos_mode: currentChaosMode,
          catch_up_enabled: currentCatchUpEnabled,
          dealer_mode: currentDealerMode,
          dealer_rolls_per_day: typeof currentDealerRollsPerDay === 'number' ? currentDealerRollsPerDay : undefined,
          daily_nomination_limit: typeof currentDailyNominationLimit === 'number'
            ? currentDailyNominationLimit
            : currentDailyNominationLimit === ''
            ? null
            : undefined,
          timezone: currentTimezone,
          selection_days: currentSelectionDays,
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

  if (group?.is_global) {
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

          {!user?.is_admin ? (
            <Text size="sm" c="dimmed">
              The global group's settings are managed by site admins only.
            </Text>
          ) : (
            <Stack gap="md">
              <Title order={5}>Dealer mode</Title>
              <Text size="sm" c="dimmed">
                The global group has no owner or admin tier of its own, so only site admins
                can change its settings — and dealer mode is the only setting that can be
                changed here.
              </Text>
              <Switch
                label="Dealer mode"
                description="Instead of a shared daily spin, each member rolls the dice to draw albums from every group's nominations at their own pace."
                checked={currentDealerMode}
                onChange={(e) => setDealerMode(e.currentTarget.checked)}
              />
              {currentDealerMode && (
                <NumberInput
                  label="Rolls per day"
                  description="How many albums each member can draw per day (max 10)."
                  value={currentDealerRollsPerDay}
                  onChange={setDealerRollsPerDay}
                  min={1}
                  max={10}
                  w={120}
                />
              )}
              <Button
                style={{ alignSelf: 'flex-start' }}
                loading={updateGroup.isPending}
                onClick={handleSaveGlobalDealer}
              >
                Save
              </Button>
            </Stack>
          )}
        </Stack>
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
          <Select
            label="Who can nominate albums"
            description="Minimum role required to add nominations to the pool. Use 'Owner' or 'Admin' to restrict to privileged members only."
            data={ROLE_OPTIONS}
            value={currentMinRoleToNominate}
            onChange={(val) => val && setMinRoleToNominate(val)}
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
            disabled={currentDealerMode}
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
          <NumberInput
            label="Max nominations per user per day"
            description="Limit how many albums each member can nominate per day. Leave empty for no limit."
            value={currentDailyNominationLimit}
            onChange={setDailyNominationLimit}
            min={1}
            max={50}
            placeholder="No limit"
            w={160}
            allowDecimal={false}
          />
          <Switch
            label="Enable guessing game"
            description="Members can guess who nominated each day's album before the reveal. Disable to skip guessing entirely."
            checked={currentAllowGuessing}
            onChange={(e) => setAllowGuessing(e.currentTarget.checked)}
          />
          <Switch
            label="Chaos mode"
            description="Each daily spin has a small chance of pulling a random album from outside the group's nominations."
            checked={currentChaosMode}
            onChange={(e) => setChaosMode(e.currentTarget.checked)}
            disabled={currentDealerMode}
          />
          <Switch
            label="Catch-up mode"
            description="On the Today's Spin tab, show up to 10 recent unreviewed albums alongside today's spin so members can catch up on missed reviews."
            checked={currentCatchUpEnabled}
            onChange={(e) => setCatchUpEnabled(e.currentTarget.checked)}
            disabled={currentDealerMode}
          />
          <Switch
            label="Dealer mode"
            description="Instead of a shared daily spin, each member rolls the dice to draw albums from the pool at their own pace. Replaces the shared selection settings while enabled."
            checked={currentDealerMode}
            onChange={(e) => setDealerMode(e.currentTarget.checked)}
          />
          {currentDealerMode && (
            <NumberInput
              label="Rolls per day"
              description="How many albums each member can draw per day (max 10)."
              value={currentDealerRollsPerDay}
              onChange={setDealerRollsPerDay}
              min={1}
              max={10}
              w={120}
            />
          )}
          <Select
            label="Timezone"
            description="When midnight resets the daily spin for this group."
            data={TIMEZONE_OPTIONS}
            value={currentTimezone}
            onChange={(val) => val && setTimezone(val)}
            allowDeselect={false}
            w={220}
          />
          <Stack gap={6}>
            <Text size="sm" fw={500}>Selection days</Text>
            <Text size="xs" c="dimmed">Albums are drawn only on checked days. Use "Albums per day" to control how many are drawn each scheduled day.</Text>
            <Chip.Group
              multiple
              value={currentSelectionDays.map(String)}
              onChange={(vals) => setSelectionDays(vals.map(Number))}
            >
              <Group gap="xs">
                {DAY_OPTIONS.map((d) => (
                  <Chip key={d.value} value={d.value} size="sm" disabled={currentDealerMode}>
                    {d.label}
                  </Chip>
                ))}
              </Group>
            </Chip.Group>
          </Stack>
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
