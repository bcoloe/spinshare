import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
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
import { IconMicrophone2, IconSearch } from '@tabler/icons-react'
import AppShell from '../../components/layout/AppShell'
import ExploreNavTabs from '../../components/explore/ExploreNavTabs'
import { useExploreArtists } from '../../hooks/useExplore'
import { artistPath } from '../../utils/artistPath'
import type { ExploreArtistItem, ExploreArtistsSort } from '../../types/explore'

const SORT_OPTIONS: { label: string; value: ExploreArtistsSort }[] = [
  { label: 'A–Z', value: 'name' },
  { label: 'Most Nominated', value: 'most_nominated' },
]

interface ArtistCardProps {
  artist: ExploreArtistItem
  onClick: () => void
}

function ArtistCard({ artist, onClick }: ArtistCardProps) {
  return (
    <Paper withBorder p="sm" onClick={onClick} style={{ cursor: 'pointer' }}>
      <Group justify="space-between" wrap="nowrap">
        <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
          <IconMicrophone2
            size={20}
            style={{ flexShrink: 0, color: 'var(--mantine-color-violet-4)' }}
          />
          <Text size="sm" fw={600} lineClamp={1}>{artist.artist}</Text>
        </Group>
        <Stack gap={2} align="flex-end" style={{ flexShrink: 0 }}>
          <Text size="xs" c="dimmed">
            {artist.album_count} {artist.album_count === 1 ? 'album' : 'albums'}
          </Text>
          <Text size="xs" c="dimmed">
            {artist.nomination_count} {artist.nomination_count === 1 ? 'nomination' : 'nominations'}
          </Text>
        </Stack>
      </Group>
    </Paper>
  )
}

export default function ExploreArtistsPage() {
  const navigate = useNavigate()
  const [sortBy, setSortBy] = useState<ExploreArtistsSort>('name')
  const [searchInput, setSearchInput] = useState('')
  const [debouncedSearch] = useDebouncedValue(searchInput, 300)

  const {
    data,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useExploreArtists({
    sort_by: sortBy,
    q: debouncedSearch || null,
  })

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

  const artists = data?.pages.flatMap((p) => p.items) ?? []

  return (
    <AppShell>
      <Stack gap="sm">
        <Group gap="xs" align="center">
          <IconMicrophone2 size={22} />
          <Title order={3}>Explore</Title>
        </Group>

        <ExploreNavTabs />

        <Stack gap="xs">
          <TextInput
            placeholder="Search artists…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.currentTarget.value)}
            leftSection={<IconSearch size={14} />}
            rightSection={isLoading && searchInput ? <Loader size="xs" /> : null}
          />
          <SegmentedControl
            size="xs"
            value={sortBy}
            onChange={(v) => setSortBy(v as ExploreArtistsSort)}
            data={SORT_OPTIONS}
          />
        </Stack>

        <div
          ref={scrollContainerRef}
          style={{ overflowY: 'auto', maxHeight: 'calc(100vh - 310px)' }}
        >
          <Stack gap="xs">
            {isLoading
              ? Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} h={56} radius="sm" />)
              : artists.map((artist) => (
                  <ArtistCard
                    key={artist.artist}
                    artist={artist}
                    onClick={() => navigate(artistPath(artist.artist))}
                  />
                ))}

            {!isLoading && artists.length === 0 && (
              <Text c="dimmed" size="sm" ta="center" mt="xl">
                No artists found. Try a different search.
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
