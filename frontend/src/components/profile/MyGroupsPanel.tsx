import { useMemo, useState } from 'react'
import { Stack, Text, TextInput } from '@mantine/core'
import { IconSearch } from '@tabler/icons-react'
import GroupsTable from './GroupsTable'
import { useAuth } from '../../hooks/useAuth'
import { useMyGroups } from '../../hooks/useGroups'
import { useMyGroupActivity } from '../../hooks/useUserProfile'
import { useFavoriteGroup } from '../../context/FavoriteGroupContext'

export default function MyGroupsPanel() {
  const { user } = useAuth()
  const { data: groups = [], isLoading } = useMyGroups(user?.username ?? '')
  const { data: activity } = useMyGroupActivity(!!user)
  const [filter, setFilter] = useState('')
  const { favoriteId, toggleFavorite } = useFavoriteGroup()

  const activityById = useMemo(
    () => new Map((activity ?? []).map((a) => [a.group_id, a])),
    [activity],
  )

  const filterLower = filter.toLowerCase()
  const filtered = filterLower
    ? groups.filter((g) => g.name.toLowerCase().includes(filterLower))
    : groups

  return (
    <Stack gap="lg">
      {!isLoading && groups.length > 0 && (
        <TextInput
          placeholder="Filter groups..."
          leftSection={<IconSearch size={16} />}
          value={filter}
          onChange={(e) => setFilter(e.currentTarget.value)}
        />
      )}

      {!isLoading && groups.length > 0 && filtered.length === 0 ? (
        <Text c="dimmed">No groups match &ldquo;{filter}&rdquo;.</Text>
      ) : (
        <GroupsTable
          ownProfile
          loading={isLoading}
          groups={filtered}
          activityById={activityById}
          favoriteId={favoriteId}
          onToggleFavorite={toggleFavorite}
          emptyMessage="You haven't joined any groups yet. Use the sidebar to find or create one."
        />
      )}
    </Stack>
  )
}
