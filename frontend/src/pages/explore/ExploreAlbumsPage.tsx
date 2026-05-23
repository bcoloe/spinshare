import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Badge,
  Group,
  Image,
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
import { IconDisc, IconSearch } from '@tabler/icons-react'
import AppShell from '../../components/layout/AppShell'
import ExploreNavTabs from '../../components/explore/ExploreNavTabs'
import { useExploreAlbums } from '../../hooks/useExplore'
import { ratingColor } from '../../utils/ratingColor'
import type { ExploreAlbumItem } from '../../types/explore'

const SORT_OPTIONS = [
  { label: 'Top Rated', value: 'top_rated' },
  { label: 'Bottom Rated', value: 'bottom_rated' },
  { label: 'Most Reviewed', value: 'most_reviewed' },
  { label: 'Most Nominated', value: 'most_nominated' },
  { label: 'Recent', value: 'recent' },
]


interface AlbumCardProps {
  album: ExploreAlbumItem
  onClick: () => void
}

function AlbumCard({ album, onClick }: AlbumCardProps) {
  return (
    <Paper withBorder p="sm" onClick={onClick} style={{ cursor: 'pointer' }}>
      <Group justify="space-between" wrap="nowrap">
        <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
          <Image
            src={album.cover_url ?? undefined}
            w={64}
            h={64}
            radius="sm"
            style={{ flexShrink: 0 }}
            fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='64' height='64'%3E%3Crect width='64' height='64' fill='%23373A40'/%3E%3Ccircle cx='32' cy='32' r='12' fill='%23555'/%3E%3C/svg%3E"
          />
          <div style={{ minWidth: 0 }}>
            <Text size="sm" fw={600} lineClamp={1}>{album.title}</Text>
            <Text size="xs" c="dimmed" lineClamp={1}>{album.artist}</Text>
            {album.release_date && (
              <Text size="xs" c="dimmed">{album.release_date.slice(0, 4)}</Text>
            )}
          </div>
        </Group>
        <Group gap="xs" style={{ flexShrink: 0 }} align="center">
          {album.avg_rating != null && (
            <Badge color={ratingColor(album.avg_rating)} variant="filled" size="sm">
              {album.avg_rating.toFixed(1)}
            </Badge>
          )}
          <Stack gap={2} align="flex-end">
            <Text size="xs" c="dimmed">
              {album.review_count} {album.review_count === 1 ? 'review' : 'reviews'}
            </Text>
            <Text size="xs" c="dimmed">
              {album.nomination_count} {album.nomination_count === 1 ? 'nomination' : 'nominations'}
            </Text>
          </Stack>
        </Group>
      </Group>
    </Paper>
  )
}

export default function ExploreAlbumsPage() {
  const navigate = useNavigate()
  const [sortBy, setSortBy] = useState('top_rated')
  const [searchInput, setSearchInput] = useState('')
  const [debouncedSearch] = useDebouncedValue(searchInput, 300)

  const {
    data,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useExploreAlbums({
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

  const albums = data?.pages.flatMap((p) => p.items) ?? []

  return (
    <AppShell>
      <Stack gap="sm">
        <Group gap="xs" align="center">
          <IconDisc size={22} />
          <Title order={3}>Explore</Title>
        </Group>

        <ExploreNavTabs />

        <Stack gap="xs">
          <TextInput
            placeholder="Search artist or album title…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.currentTarget.value)}
            leftSection={<IconSearch size={14} />}
            rightSection={isLoading && searchInput ? <Loader size="xs" /> : null}
          />
          <SegmentedControl
            size="xs"
            value={sortBy}
            onChange={setSortBy}
            data={SORT_OPTIONS}
          />
        </Stack>

        <div
          ref={scrollContainerRef}
          style={{ overflowY: 'auto', maxHeight: 'calc(100vh - 310px)' }}
        >
          <Stack gap="xs">
            {isLoading
              ? Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} h={80} radius="sm" />)
              : albums.map((album) => (
                  <AlbumCard
                    key={album.id}
                    album={album}
                    onClick={() => navigate(`/albums/${album.id}`)}
                  />
                ))}

            {!isLoading && albums.length === 0 && (
              <Text c="dimmed" size="sm" ta="center" mt="xl">
                No albums found. Try a different search or sort.
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
