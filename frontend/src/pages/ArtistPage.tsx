import { useParams, Link } from 'react-router-dom'
import {
  Badge,
  Group,
  Paper,
  SimpleGrid,
  Skeleton,
  Stack,
  Text,
  Title,
  UnstyledButton,
} from '@mantine/core'
import { IconMicrophone2, IconMusic } from '@tabler/icons-react'
import AppShell from '../components/layout/AppShell'
import { ratingColor } from '../utils/ratingColor'
import { useArtistOverview } from '../hooks/useArtist'
import type { ArtistAlbumItem } from '../types/artist'

// ==================== STAT CARD ====================

interface StatCardProps {
  label: string
  value: number | string
  sub?: string
  loading: boolean
}

function StatCard({ label, value, sub, loading }: StatCardProps) {
  return (
    <Paper withBorder p="md" radius="md">
      {loading ? (
        <Skeleton h={40} />
      ) : (
        <Stack gap={4}>
          <Group gap={6} align="baseline" wrap="nowrap">
            <Text size="xl" fw={700}>{value}</Text>
            {sub && <Text size="xs" c="dimmed">{sub}</Text>}
          </Group>
          <Text size="xs" c="dimmed">{label}</Text>
        </Stack>
      )}
    </Paper>
  )
}

// ==================== ALBUM ROW ====================

function releaseYear(release_date: string | null | undefined): string | null {
  return release_date ? String(release_date).slice(0, 4) : null
}

function AlbumRow({ item }: { item: ArtistAlbumItem }) {
  const { album, nomination_count, review_count, average_rating } = item
  const year = releaseYear(album.release_date)

  return (
    <UnstyledButton component={Link} to={`/albums/${album.id}`} w="100%">
      <Paper withBorder p="sm" radius="md" style={{ transition: 'background 120ms' }}>
        <Group gap="md" wrap="nowrap">
          {album.cover_url ? (
            <img
              src={album.cover_url}
              width={52}
              height={52}
              style={{ borderRadius: 6, flexShrink: 0, objectFit: 'cover' }}
            />
          ) : (
            <div
              style={{
                width: 52,
                height: 52,
                background: 'var(--mantine-color-dark-5)',
                borderRadius: 6,
                flexShrink: 0,
              }}
            />
          )}

          <Stack gap={2} style={{ flex: 1, minWidth: 0 }}>
            <Text size="sm" fw={600} lineClamp={1}>{album.title}</Text>
            <Group gap="xs">
              {year && <Text size="xs" c="dimmed">{year}</Text>}
              <Text size="xs" c="dimmed">
                {nomination_count} {nomination_count === 1 ? 'nomination' : 'nominations'}
              </Text>
              <Text size="xs" c="dimmed">·</Text>
              <Text size="xs" c="dimmed">
                {review_count} {review_count === 1 ? 'review' : 'reviews'}
              </Text>
            </Group>
          </Stack>

          <Stack gap={2} align="center" style={{ flexShrink: 0 }}>
            <Badge
              size="lg"
              variant="light"
              color={average_rating !== null ? ratingColor(average_rating) : 'gray'}
            >
              {average_rating !== null ? average_rating.toFixed(1) : '—'}
            </Badge>
            {item.rating_stddev != null && review_count >= 2 && (
              <Text size="xs" c="dimmed">± {item.rating_stddev.toFixed(1)}</Text>
            )}
          </Stack>
        </Group>
      </Paper>
    </UnstyledButton>
  )
}

// ==================== MAIN PAGE ====================

export default function ArtistPage() {
  const { artistName: artistNameParam } = useParams<{ artistName: string }>()
  const artistName = decodeURIComponent(artistNameParam ?? '')
  const { data: overview, isLoading, isError } = useArtistOverview(artistName)

  // The artist-level ±1σ (spread of album averages) is only meaningful once at
  // least two albums carry a rating.
  const ratedAlbumCount = overview?.albums.filter((a) => a.average_rating != null).length ?? 0

  return (
    <AppShell>
      <Stack gap="lg">
        {/* ── HEADER ── */}
        <Group gap="md" align="center" wrap="nowrap">
          <IconMicrophone2 size={36} style={{ flexShrink: 0, color: 'var(--mantine-color-violet-4)' }} />
          <Stack gap={2} style={{ minWidth: 0 }}>
            {isLoading ? (
              <Skeleton h={30} w={220} />
            ) : (
              <Title order={2} lineClamp={2}>{overview?.artist ?? artistName}</Title>
            )}
            <Text size="sm" c="dimmed">Artist</Text>
          </Stack>
        </Group>

        {isError ? (
          <Paper withBorder p="xl" radius="md">
            <Stack gap="xs" align="center">
              <IconMusic size={28} style={{ color: 'var(--mantine-color-dimmed)' }} />
              <Text c="dimmed" ta="center">
                No nominated albums found for this artist yet.
              </Text>
            </Stack>
          </Paper>
        ) : (
          <>
            {/* ── STAT CARDS ── */}
            <SimpleGrid cols={{ base: 2, sm: 4 }}>
              <StatCard label="Albums" value={overview?.album_count ?? 0} loading={isLoading} />
              <StatCard label="Nominations" value={overview?.total_nominations ?? 0} loading={isLoading} />
              <StatCard label="Reviews" value={overview?.total_reviews ?? 0} loading={isLoading} />
              <StatCard
                label="Avg score"
                value={overview?.average_rating != null ? overview.average_rating.toFixed(1) : '—'}
                sub={
                  overview?.rating_stddev != null && ratedAlbumCount >= 2
                    ? `± ${overview.rating_stddev.toFixed(1)} (1σ)`
                    : undefined
                }
                loading={isLoading}
              />
            </SimpleGrid>

            {/* ── NOMINATED ALBUMS (descending mean score) ── */}
            <Stack gap="sm">
              <Text fw={600} size="sm">Nominated albums</Text>
              {isLoading ? (
                <Stack gap="xs">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} h={72} radius="md" />
                  ))}
                </Stack>
              ) : overview && overview.albums.length > 0 ? (
                <Stack gap="xs">
                  {overview.albums.map((item) => (
                    <AlbumRow key={item.album.id} item={item} />
                  ))}
                </Stack>
              ) : (
                <Text c="dimmed" size="sm">No nominated albums yet.</Text>
              )}
            </Stack>
          </>
        )}
      </Stack>
    </AppShell>
  )
}
