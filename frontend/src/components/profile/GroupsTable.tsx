import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ActionIcon,
  Avatar,
  Badge,
  Button,
  Group,
  Loader,
  Skeleton,
  Stack,
  Table,
  Text,
  UnstyledButton,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useQuery } from '@tanstack/react-query'
import {
  IconBolt,
  IconChevronDown,
  IconChevronRight,
  IconDice5,
  IconStar,
  IconStarFilled,
} from '@tabler/icons-react'
import { useJoinGroup } from '../../hooks/useGroups'
import { groupService } from '../../services/groupService'
import { ApiError } from '../../services/apiClient'
import type { UserGroupItem } from '../../types/auth'
import type { GroupActivityItem } from '../../types/group'

// A group "has activity" when the viewer can act on it today: an unreviewed
// shared spin, or dealer rolls still available. Only meaningful on own profile.
function hasActivity(a: GroupActivityItem | undefined): boolean {
  if (!a) return false
  return a.unreviewed_today > 0 || (a.rolls_remaining ?? 0) > 0
}

function ActivityBadge({ activity }: { activity?: GroupActivityItem }) {
  if (!activity) return null
  if ((activity.rolls_remaining ?? 0) > 0) {
    return (
      <Badge size="sm" variant="light" color="yellow" leftSection={<IconDice5 size={12} />}>
        {activity.rolls_remaining} roll{activity.rolls_remaining !== 1 ? 's' : ''}
      </Badge>
    )
  }
  if (activity.unreviewed_today > 0) {
    return (
      <Badge size="sm" variant="light" color="yellow" leftSection={<IconBolt size={12} />}>
        New
      </Badge>
    )
  }
  return null
}

interface GroupRowProps {
  group: UserGroupItem
  ownProfile: boolean
  activity?: GroupActivityItem
  isFavorite: boolean
  onToggleFavorite?: (groupId: number) => void
}

function GroupRow({ group, ownProfile, activity, isFavorite, onToggleFavorite }: GroupRowProps) {
  const [expanded, setExpanded] = useState(false)
  const navigate = useNavigate()
  const joinGroup = useJoinGroup()
  const inCommon = group.current_user_role !== null

  // Highlight semantics differ by context: activity (yellow) on your own
  // profile, shared-membership (green) when viewing someone else.
  const highlighted = ownProfile ? hasActivity(activity) : inCommon
  const highlightColor = ownProfile ? 'yellow.4' : 'green.4'

  const { data: members = [], isFetching: membersFetching } = useQuery({
    queryKey: ['groups', group.id, 'members'],
    queryFn: () => groupService.getMembers(group.id),
    enabled: expanded,
  })

  const handleJoin = async (e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await joinGroup.mutateAsync(group.id)
      notifications.show({ color: 'green', message: `Joined "${group.name}"` })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not join group'
      notifications.show({ color: 'red', message })
    }
  }

  return (
    <>
      <Table.Tr style={{ cursor: 'pointer' }} onClick={() => navigate(`/groups/${group.id}`)}>
        <Table.Td w={28} onClick={(e) => e.stopPropagation()}>
          <ActionIcon
            variant="subtle"
            color="gray"
            size="sm"
            onClick={() => setExpanded((v) => !v)}
            aria-label={expanded ? 'Hide members' : 'Show members'}
          >
            {expanded ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
          </ActionIcon>
        </Table.Td>
        <Table.Td>
          <Group gap="xs" wrap="nowrap">
            <Text size="sm" fw={highlighted ? 700 : 400} c={highlighted ? highlightColor : undefined}>
              {group.name}
            </Text>
            {ownProfile && <ActivityBadge activity={activity} />}
          </Group>
        </Table.Td>
        <Table.Td>
          <Text size="sm" c="dimmed">
            {group.member_count} member{group.member_count !== 1 ? 's' : ''}
          </Text>
        </Table.Td>
        <Table.Td onClick={(e) => e.stopPropagation()}>
          {ownProfile ? (
            <ActionIcon
              size="sm"
              variant="subtle"
              color={isFavorite ? 'yellow' : 'gray'}
              onClick={() => onToggleFavorite?.(group.id)}
              aria-label={isFavorite ? 'Unset default group' : 'Set as default group'}
            >
              {isFavorite ? <IconStarFilled size={14} /> : <IconStar size={14} />}
            </ActionIcon>
          ) : inCommon ? (
            <Badge size="sm" variant="light" color="green">
              {group.current_user_role}
            </Badge>
          ) : (
            <Button size="xs" variant="light" loading={joinGroup.isPending} onClick={handleJoin}>
              Join
            </Button>
          )}
        </Table.Td>
      </Table.Tr>

      {expanded && (
        <Table.Tr>
          <Table.Td />
          <Table.Td
            colSpan={3}
            style={{ background: 'var(--mantine-color-dark-7)', padding: '10px 16px' }}
          >
            {membersFetching ? (
              <Loader size="xs" />
            ) : members.length === 0 ? (
              <Text size="xs" c="dimmed">No members found.</Text>
            ) : (
              <Group gap="xs" wrap="wrap">
                {members.map((m) => (
                  <UnstyledButton
                    key={m.user_id}
                    onClick={(e) => { e.stopPropagation(); navigate(`/users/${m.username}`) }}
                  >
                    <Group gap={6}>
                      <Avatar size="xs" radius="xl" color="violet">
                        {m.username[0].toUpperCase()}
                      </Avatar>
                      <Text
                        size="xs"
                        onMouseEnter={(e) => { e.currentTarget.style.textDecoration = 'underline' }}
                        onMouseLeave={(e) => { e.currentTarget.style.textDecoration = 'none' }}
                      >
                        {m.username}
                      </Text>
                    </Group>
                  </UnstyledButton>
                ))}
              </Group>
            )}
          </Table.Td>
        </Table.Tr>
      )}
    </>
  )
}

interface Props {
  groups: UserGroupItem[]
  loading: boolean
  /** Own-profile mode: yellow activity highlighting + badges + default-group star. */
  ownProfile?: boolean
  activityById?: Map<number, GroupActivityItem>
  favoriteId?: number | null
  onToggleFavorite?: (groupId: number) => void
  emptyMessage?: string
}

export default function GroupsTable({
  groups,
  loading,
  ownProfile = false,
  activityById,
  favoriteId = null,
  onToggleFavorite,
  emptyMessage = 'No public groups.',
}: Props) {
  if (loading) {
    return (
      <Stack gap="xs">
        {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} h={44} radius="sm" />)}
      </Stack>
    )
  }

  if (groups.length === 0) {
    return <Text size="sm" c="dimmed">{emptyMessage}</Text>
  }

  const sorted = [...groups].sort((a, b) => {
    // Prioritized rows first (activity on own profile, shared membership elsewhere),
    // then alphabetical.
    const aPriority = ownProfile ? hasActivity(activityById?.get(a.id)) : a.current_user_role !== null
    const bPriority = ownProfile ? hasActivity(activityById?.get(b.id)) : b.current_user_role !== null
    if (aPriority !== bPriority) return aPriority ? -1 : 1
    return a.name.localeCompare(b.name)
  })

  return (
    <Table highlightOnHover verticalSpacing="sm">
      <Table.Thead>
        <Table.Tr>
          <Table.Th w={28} />
          <Table.Th><Text size="xs" c="dimmed">Name</Text></Table.Th>
          <Table.Th><Text size="xs" c="dimmed">Members</Text></Table.Th>
          <Table.Th />
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {sorted.map((g) => (
          <GroupRow
            key={g.id}
            group={g}
            ownProfile={ownProfile}
            activity={activityById?.get(g.id)}
            isFavorite={favoriteId === g.id}
            onToggleFavorite={onToggleFavorite}
          />
        ))}
      </Table.Tbody>
    </Table>
  )
}
