import { useState } from 'react'
import { ActionIcon, Button, Divider, Group, SimpleGrid, Skeleton, Stack, Text, TextInput, Title } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { IconPlus, IconSearch, IconStar, IconStarFilled } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/layout/AppShell'
import MyNominationsPool from '../components/profile/MyNominationsPool'
import AlbumSearchModal from '../components/albums/AlbumSearchModal'
import { useAuth } from '../hooks/useAuth'
import { useMyGroups } from '../hooks/useGroups'
import { useFavoriteGroup } from '../context/FavoriteGroupContext'

export default function DashboardPage() {
  const { user } = useAuth()
  const { data: groups, isLoading } = useMyGroups(user?.username ?? '')
  const navigate = useNavigate()
  const [filter, setFilter] = useState('')
  const { favoriteId, toggleFavorite } = useFavoriteGroup()
  const [nominateOpened, { open: openNominate, close: closeNominate }] = useDisclosure(false)

  const filterLower = filter.toLowerCase()
  const sorted = [...(groups ?? [])].sort((a, b) => a.name.localeCompare(b.name))
  const filtered = filterLower ? sorted.filter((g) => g.name.toLowerCase().includes(filterLower)) : sorted

  return (
    <AppShell>
      <Stack gap="xl">
        <Stack gap="lg">
          <Group justify="space-between" align="center">
            <Title order={3}>Your Groups</Title>
          </Group>

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
                  <Group justify="space-between" align="flex-start">
                    <Text fw={600}>{g.name}</Text>
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
                  <Text size="xs" c="dimmed">{g.member_count} member{g.member_count !== 1 ? 's' : ''}</Text>
                </Stack>
              ))}
            </SimpleGrid>
          )}
        </Stack>

        <Divider />

        <Stack gap="lg">
          <Group justify="space-between" align="center">
            <Title order={3}>My Nominations</Title>
            <Button leftSection={<IconPlus size={16} />} size="sm" onClick={openNominate}>
              Add Nomination
            </Button>
          </Group>
          <MyNominationsPool />
        </Stack>
      </Stack>

      <AlbumSearchModal opened={nominateOpened} onClose={closeNominate} />
    </AppShell>
  )
}
