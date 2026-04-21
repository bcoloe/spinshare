import { Button, Group, SimpleGrid, Skeleton, Stack, Text, Title } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { IconPlus, IconSearch } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/layout/AppShell'
import CreateGroupModal from '../components/groups/CreateGroupModal'
import JoinGroupModal from '../components/groups/JoinGroupModal'
import { useAuth } from '../hooks/useAuth'
import { useMyGroups } from '../hooks/useGroups'

export default function DashboardPage() {
  const { user } = useAuth()
  const { data: groups, isLoading } = useMyGroups(user?.username ?? '')
  const navigate = useNavigate()
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure()
  const [joinOpened, { open: openJoin, close: closeJoin }] = useDisclosure()

  return (
    <AppShell>
      <Stack gap="lg">
        <Group justify="space-between">
          <Title order={3}>Your Groups</Title>
          <Group gap="xs">
            <Button size="sm" variant="light" leftSection={<IconSearch size={16} />} onClick={openJoin}>
              Find group
            </Button>
            <Button size="sm" leftSection={<IconPlus size={16} />} onClick={openCreate}>
              New group
            </Button>
          </Group>
        </Group>

        {isLoading ? (
          <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
            {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} h={100} radius="md" />)}
          </SimpleGrid>
        ) : groups?.length === 0 ? (
          <Text c="dimmed">You haven&apos;t joined any groups yet.</Text>
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

      <CreateGroupModal opened={createOpened} onClose={closeCreate} />
      <JoinGroupModal opened={joinOpened} onClose={closeJoin} />
    </AppShell>
  )
}
