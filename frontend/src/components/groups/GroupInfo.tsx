import { useNavigate } from 'react-router-dom'
import { Badge, Button, Divider, Group, SimpleGrid, Skeleton, Stack, Text, Title } from '@mantine/core'
import { IconListDetails } from '@tabler/icons-react'
import MemberList from './MemberList'
import { useGroupStats, useGroupPendingInvitations } from '../../hooks/useGroups'
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

  const canManage =
    group.current_user_role === 'owner' || group.current_user_role === 'admin'

  const { data: pendingInvitations = [] } = useGroupPendingInvitations(group.id, canManage)

  const canManageCatalog = canManage

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

      {canManage && pendingInvitations.length > 0 && (
        <>
          <Divider />
          <div>
            <Group gap="xs" mb="sm">
              <Title order={5}>Pending Invitations</Title>
              <Badge size="sm" variant="light" color="violet">{pendingInvitations.length}</Badge>
            </Group>
            <Stack gap="xs">
              {pendingInvitations.map((inv) => (
                <Group key={inv.id} justify="space-between">
                  <Text size="sm">{inv.invited_email}</Text>
                  <Text size="xs" c="dimmed">
                    invited by {inv.inviter_username} · expires{' '}
                    {new Date(inv.expires_at).toLocaleDateString()}
                  </Text>
                </Group>
              ))}
            </Stack>
          </div>
        </>
      )}

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
