import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Badge,
  Group,
  Loader,
  Paper,
  SegmentedControl,
  Skeleton,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { IconSearch, IconUsersGroup } from '@tabler/icons-react'
import AppShell from '../../components/layout/AppShell'
import ExploreNavTabs from '../../components/explore/ExploreNavTabs'
import { useExploreGroups } from '../../hooks/useExplore'
import type { ExploreGroupItem, ExploreGroupsParams } from '../../types/explore'

const TYPE_OPTIONS = [
  { label: 'All', value: 'all' },
  { label: 'Human', value: 'human' },
  { label: 'Bot', value: 'bot' },
]

interface GroupCardProps {
  group: ExploreGroupItem
  onClick: () => void
}

function GroupCard({ group, onClick }: GroupCardProps) {
  const formattedDate = new Date(group.created_at).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
  })

  return (
    <Paper withBorder p="sm" onClick={onClick} style={{ cursor: 'pointer' }}>
      <Group justify="space-between" wrap="nowrap">
        <div style={{ minWidth: 0 }}>
          <Group gap="xs" wrap="nowrap">
            <Text size="sm" fw={600} lineClamp={1}>{group.name}</Text>
            {group.is_global && (
              <Badge size="xs" color="violet" variant="light">Bot</Badge>
            )}
          </Group>
          <Text size="xs" c="dimmed">
            {group.member_count} {group.member_count === 1 ? 'member' : 'members'} · formed {formattedDate}
          </Text>
        </div>
      </Group>
    </Paper>
  )
}

export default function ExploreGroupsPage() {
  const navigate = useNavigate()
  const [searchInput, setSearchInput] = useState('')
  const [groupType, setGroupType] = useState<'all' | 'human' | 'bot'>('all')
  const [debouncedSearch] = useDebouncedValue(searchInput, 300)

  const filters: Omit<ExploreGroupsParams, 'offset'> = {
    q: debouncedSearch || null,
    group_type: groupType,
  }

  const {
    data,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useExploreGroups(filters)

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

  const groups = data?.pages.flatMap((p) => p.items) ?? []

  return (
    <AppShell>
      <Stack gap="sm">
        <Group gap="xs" align="center">
          <IconUsersGroup size={22} />
          <Title order={3}>Explore</Title>
        </Group>

        <ExploreNavTabs />

        <Stack gap="xs">
          <TextInput
            placeholder="Search groups by name…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.currentTarget.value)}
            leftSection={<IconSearch size={14} />}
            rightSection={isLoading && searchInput ? <Loader size="xs" /> : null}
          />
          <SegmentedControl
            size="xs"
            value={groupType}
            onChange={(v) => setGroupType(v as 'all' | 'human' | 'bot')}
            data={TYPE_OPTIONS}
          />
        </Stack>

        <div
          ref={scrollContainerRef}
          style={{ overflowY: 'auto', maxHeight: 'calc(100vh - 310px)' }}
        >
          <Stack gap="xs">
            {isLoading
              ? Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} h={60} radius="sm" />)
              : groups.map((group) => (
                  <GroupCard
                    key={group.id}
                    group={group}
                    onClick={() => navigate(`/groups/${group.id}`)}
                  />
                ))}

            {!isLoading && groups.length === 0 && (
              <Text c="dimmed" size="sm" ta="center" mt="xl">
                No groups found. Try a different search or filter.
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
