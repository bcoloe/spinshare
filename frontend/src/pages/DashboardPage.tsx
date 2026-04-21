import { SimpleGrid, Skeleton, Stack, Text, Title } from '@mantine/core'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/layout/AppShell'
import { useAuth } from '../hooks/useAuth'
import { useMyGroups } from '../hooks/useGroups'

export default function DashboardPage() {
  const { user } = useAuth()
  const { data: groups, isLoading } = useMyGroups(user?.username ?? '')
  const navigate = useNavigate()

  return (
    <AppShell>
      <Stack gap="lg">
        <Title order={3}>Your Groups</Title>

        {isLoading ? (
          <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
            {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} h={100} radius="md" />)}
          </SimpleGrid>
        ) : groups?.length === 0 ? (
          <Text c="dimmed">You haven&apos;t joined any groups yet. Use the sidebar to find or create one.</Text>
        ) : (
          <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
            {groups?.map((g) => (
              <Stack
                key={g.id}
                p="md"
                style={{ border: '1px solid var(--mantine-color-dark-4)', borderRadius: 8, cursor: 'pointer' }}
                onClick={() => navigate(`/groups/${g.id}`)}
                gap="xs"
              >
                <Text fw={600}>{g.name}</Text>
                <Text size="xs" c="dimmed">{g.member_count} member{g.member_count !== 1 ? 's' : ''}</Text>
              </Stack>
            ))}
          </SimpleGrid>
        )}
      </Stack>
    </AppShell>
  )
}
