import { Progress, Skeleton, Stack, Text } from '@mantine/core'
import { useMyGuessStats } from '../../hooks/useStats'
import { useAuth } from '../../hooks/useAuth'
import type { GroupDetailResponse } from '../../types/group'

interface Props {
  groups: GroupDetailResponse[]
}

function GroupGuessRow({ group, userId }: { group: GroupDetailResponse; userId: number }) {
  const { data: stats, isLoading } = useMyGuessStats(group.id, userId)

  if (isLoading) return <Skeleton h={40} radius="sm" />

  const pct = stats ? Math.round(stats.accuracy * 100) : 0

  return (
    <Stack gap={4}>
      <Text size="sm" fw={500}>{group.name}</Text>
      <Progress value={pct} color="violet" size="sm" />
      <Text size="xs" c="dimmed">
        {pct}% accuracy · {stats?.total_guesses ?? 0} guesses
      </Text>
    </Stack>
  )
}

export default function GroupStatsList({ groups }: Props) {
  const { user } = useAuth()

  if (!user) return null
  if (!groups.length) return <Text size="sm" c="dimmed">No groups yet.</Text>

  return (
    <Stack gap="md">
      {groups
        .slice()
        .sort((a, b) => a.name.localeCompare(b.name))
        .map((g) => (
          <GroupGuessRow key={g.id} group={g} userId={user.id} />
        ))}
    </Stack>
  )
}
