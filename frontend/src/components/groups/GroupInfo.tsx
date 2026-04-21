import { useNavigate } from 'react-router-dom'
import { Button, Divider, SimpleGrid, Skeleton, Stack, Text, Title } from '@mantine/core'
import { IconListDetails } from '@tabler/icons-react'
import MemberList from './MemberList'
import { useGroupStats } from '../../hooks/useGroups'
import type { GroupDetailResponse } from '../../types/group'

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

interface StatCardProps {
  label: string
  value: string | number
}

function StatCard({ label, value }: StatCardProps) {
  return (
    <Stack
      gap={4}
      p="md"
      style={{ border: '1px solid var(--mantine-color-dark-4)', borderRadius: 8 }}
    >
      <Text size="xl" fw={700}>{value}</Text>
      <Text size="xs" c="dimmed">{label}</Text>
    </Stack>
  )
}

interface Props {
  group: GroupDetailResponse
}

export default function GroupInfo({ group }: Props) {
  const navigate = useNavigate()
  const { data: stats, isLoading: statsLoading } = useGroupStats(group.id)

  const canManageCatalog =
    group.current_user_role === 'owner' || group.current_user_role === 'admin'

  return (
    <Stack gap="xl">
      <div>
        <Title order={5} mb="sm">Group Stats</Title>
        {statsLoading ? (
          <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="md">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} h={80} radius="md" />)}
          </SimpleGrid>
        ) : (
          <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="md">
            <StatCard label="Members" value={stats?.member_count ?? group.member_count} />
            <StatCard label="Albums Added" value={stats?.albums_added ?? '—'} />
            <StatCard label="Albums Reviewed" value={stats?.albums_reviewed ?? '—'} />
            <StatCard
              label="Formed"
              value={stats?.formed_at ? formatDate(stats.formed_at) : '—'}
            />
          </SimpleGrid>
        )}
      </div>

      <Divider />

      <div>
        <Title order={5} mb="sm">Members</Title>
        <MemberList group={group} />
      </div>

      {canManageCatalog && (
        <>
          <Divider />
          <div>
            <Title order={5} mb="sm">Catalog</Title>
            <Text size="sm" c="dimmed" mb="sm">
              Manage nominations, review pending albums, and update statuses.
            </Text>
            <Button
              variant="light"
              leftSection={<IconListDetails size={16} />}
              onClick={() => navigate(`/groups/${group.id}/catalog`)}
            >
              Open catalog
            </Button>
          </div>
        </>
      )}
    </Stack>
  )
}
