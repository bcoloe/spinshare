import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Group,
  Loader,
  Paper,
  Skeleton,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { IconSearch, IconUsers } from '@tabler/icons-react'
import AppShell from '../../components/layout/AppShell'
import ExploreNavTabs from '../../components/explore/ExploreNavTabs'
import { useExploreUsers } from '../../hooks/useExplore'
import type { ExploreUserItem, ExploreUsersParams } from '../../types/explore'

interface UserCardProps {
  user: ExploreUserItem
  onClick: () => void
}

function UserCard({ user, onClick }: UserCardProps) {
  const memberSince = new Date(user.member_since).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
  })

  return (
    <Paper withBorder p="sm" onClick={onClick} style={{ cursor: 'pointer' }}>
      <Group justify="space-between" wrap="nowrap">
        <div style={{ minWidth: 0 }}>
          <Text size="sm" fw={600} lineClamp={1}>
            {user.username}
          </Text>
          <Text size="xs" c="dimmed">
            {user.review_count} {user.review_count === 1 ? 'review' : 'reviews'} ·{' '}
            {user.total_groups} {user.total_groups === 1 ? 'group' : 'groups'} · member since{' '}
            {memberSince}
          </Text>
        </div>
      </Group>
    </Paper>
  )
}

export default function ExploreUsersPage() {
  const navigate = useNavigate()
  const [searchInput, setSearchInput] = useState('')
  const [debouncedSearch] = useDebouncedValue(searchInput, 300)

  const filters: Omit<ExploreUsersParams, 'offset'> = {
    q: debouncedSearch || null,
  }

  const {
    data,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useExploreUsers(filters)

  const sentinelRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const sentinel = sentinelRef.current
    const container = scrollContainerRef.current
    if (!sentinel || !container || !hasNextPage) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !isFetchingNextPage) fetchNextPage()
      },
      { root: container, threshold: 0 },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  const users = data?.pages.flatMap((p) => p.items) ?? []

  return (
    <AppShell>
      <Stack gap="sm">
        <Group gap="xs" align="center">
          <IconUsers size={22} />
          <Title order={3}>Explore</Title>
        </Group>

        <ExploreNavTabs />

        <TextInput
          placeholder="Search users by username…"
          value={searchInput}
          onChange={(e) => setSearchInput(e.currentTarget.value)}
          leftSection={<IconSearch size={14} />}
          rightSection={isLoading && searchInput ? <Loader size="xs" /> : null}
        />

        <div
          ref={scrollContainerRef}
          style={{ overflowY: 'auto', maxHeight: 'calc(100vh - 280px)' }}
        >
          <Stack gap="xs">
            {isLoading
              ? Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} h={60} radius="sm" />)
              : users.map((user) => (
                  <UserCard
                    key={user.id}
                    user={user}
                    onClick={() => navigate(`/users/${user.username}`)}
                  />
                ))}

            {!isLoading && users.length === 0 && (
              <Text c="dimmed" size="sm" ta="center" mt="xl">
                No users found. Try a different search.
              </Text>
            )}

            {isFetchingNextPage && (
              <Group justify="center" py="sm">
                <Loader size="sm" />
              </Group>
            )}

            <div ref={sentinelRef} style={{ height: 1 }} />
          </Stack>
        </div>
      </Stack>
    </AppShell>
  )
}
