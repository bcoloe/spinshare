import { Group, RingProgress, SimpleGrid, Skeleton, Stack, Text } from '@mantine/core'
import type { UserWithStats } from '../../types/stats'

interface StatCardProps {
  label: string
  value: number | string
}

function StatCard({ label, value }: StatCardProps) {
  return (
    <Stack gap={4} p="md" style={{ border: '1px solid var(--mantine-color-dark-4)', borderRadius: 8 }}>
      <Text size="xl" fw={700}>{value}</Text>
      <Text size="xs" c="dimmed">{label}</Text>
    </Stack>
  )
}

interface Props {
  stats: UserWithStats | undefined
  isLoading: boolean
}

export default function StatsGrid({ stats, isLoading }: Props) {
  if (isLoading) {
    return (
      <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="md">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} h={80} radius="md" />)}
      </SimpleGrid>
    )
  }

  if (!stats) return null

  return (
    <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="md">
      <StatCard label="Groups" value={stats.total_groups} />
      <StatCard label="Reviews" value={stats.total_reviews} />
      <StatCard label="Albums Added" value={stats.albums_added} />
      <StatCard label="Groups Created" value={stats.created_groups} />
    </SimpleGrid>
  )
}

interface RingProps {
  accuracy: number
  totalGuesses: number
}

export function AccuracyRing({ accuracy, totalGuesses }: RingProps) {
  const pct = Math.round(accuracy * 100)
  return (
    <Group gap="md">
      <RingProgress
        size={80}
        thickness={6}
        sections={[{ value: pct, color: 'violet' }]}
        label={
          <Text ta="center" size="xs" fw={700}>{pct}%</Text>
        }
      />
      <div>
        <Text size="sm" fw={500}>Guess accuracy</Text>
        <Text size="xs" c="dimmed">{totalGuesses} guesses</Text>
      </div>
    </Group>
  )
}
