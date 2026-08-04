import { useMemo, useState } from 'react'
import { ActionIcon, Badge, Group, SimpleGrid, Skeleton, Stack, Text, TextInput } from '@mantine/core'
import { IconDice5, IconSearch, IconStar, IconStarFilled } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useMyGroups } from '../../hooks/useGroups'
import { useMyGroupActivity } from '../../hooks/useUserProfile'
import { useFavoriteGroup } from '../../context/FavoriteGroupContext'
import type { GroupActivityItem, GroupDetailResponse } from '../../types/group'

function ActivityBadge({ group, activity }: { group: GroupDetailResponse; activity?: GroupActivityItem }) {
  // Global and bot groups never carry an action indicator.
  if (group.is_global || group.is_bot_group) return null

  if (group.settings?.dealer_mode) {
    const rolls = activity?.rolls_remaining ?? 0
    if (rolls <= 0) return null
    return (
      <Badge size="sm" variant="light" color="violet" leftSection={<IconDice5 size={12} />}>
        {rolls} roll{rolls !== 1 ? 's' : ''}
      </Badge>
    )
  }

  if ((activity?.unreviewed_today ?? 0) > 0) {
    return (
      <Badge size="sm" variant="filled" color="violet">
        New
      </Badge>
    )
  }
  return null
}

export default function MyGroupsPanel() {
  const { user } = useAuth()
  const { data: groups, isLoading } = useMyGroups(user?.username ?? '')
  const { data: activity } = useMyGroupActivity(!!user)
  const navigate = useNavigate()
  const [filter, setFilter] = useState('')
  const { favoriteId, toggleFavorite } = useFavoriteGroup()

  const activityById = useMemo(
    () => new Map((activity ?? []).map((a) => [a.group_id, a])),
    [activity],
  )

  const filterLower = filter.toLowerCase()
  const sorted = [...(groups ?? [])].sort((a, b) => a.name.localeCompare(b.name))
  const filtered = filterLower ? sorted.filter((g) => g.name.toLowerCase().includes(filterLower)) : sorted

  return (
    <Stack gap="lg">
      {!isLoading && (groups?.length ?? 0) > 0 && (
        <TextInput
          placeholder="Filter groups..."
          leftSection={<IconSearch size={16} />}
          value={filter}
          onChange={(e) => setFilter(e.currentTarget.value)}
        />
      )}

      {isLoading ? (
        <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} h={100} radius="md" />)}
        </SimpleGrid>
      ) : groups?.length === 0 ? (
        <Text c="dimmed">You haven&apos;t joined any groups yet. Use the sidebar to find or create one.</Text>
      ) : filtered.length === 0 ? (
        <Text c="dimmed">No groups match &ldquo;{filter}&rdquo;.</Text>
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
          {filtered.map((g) => (
            <Stack
              key={g.id}
              p="md"
              style={{ border: '1px solid var(--mantine-color-dark-4)', borderRadius: 8, cursor: 'pointer' }}
              onClick={() => navigate(`/groups/${g.id}`)}
              gap="xs"
            >
              <Group justify="space-between" align="flex-start" wrap="nowrap">
                <Text fw={600} lineClamp={1}>{g.name}</Text>
                <Group gap={4} wrap="nowrap">
                  <ActivityBadge group={g} activity={activityById.get(g.id)} />
                  <ActionIcon
                    size="sm"
                    variant="subtle"
                    color={favoriteId === g.id ? 'yellow' : 'gray'}
                    onClick={(e) => { e.stopPropagation(); toggleFavorite(g.id) }}
                    aria-label={favoriteId === g.id ? 'Unset default group' : 'Set as default group'}
                  >
                    {favoriteId === g.id ? <IconStarFilled size={14} /> : <IconStar size={14} />}
                  </ActionIcon>
                </Group>
              </Group>
              <Text size="xs" c="dimmed">{g.member_count} member{g.member_count !== 1 ? 's' : ''}</Text>
            </Stack>
          ))}
        </SimpleGrid>
      )}
    </Stack>
  )
}
