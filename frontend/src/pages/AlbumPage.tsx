import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  Badge,
  Box,
  Group,
  Paper,
  ScrollArea,
  Skeleton,
  Stack,
  Table,
  Text,
  Title,
  UnstyledButton,
} from '@mantine/core'
import {
  IconChevronDown,
  IconChevronRight,
  IconChevronUp,
  IconSelector,
} from '@tabler/icons-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import AppShell from '../components/layout/AppShell'
import SpotifyPlayer from '../components/spin/SpotifyPlayer'
import { useMyStats } from '../hooks/useStats'
import { useAlbumDetails, useAlbumReviews, useAlbumStats } from '../hooks/useAlbumPage'
import type { AlbumReviewItem } from '../types/album'

// ==================== TYPES ====================

type SortField = 'username' | 'date' | 'rating'
type SortDir = 'asc' | 'desc'

// ==================== HELPERS ====================

function ratingColor(rating: number): string {
  if (rating < 3) return 'red.7'
  if (rating < 5) return '#6b4226'
  if (rating < 7) return 'orange.5'
  if (rating < 9) return 'lime.5'
  return 'green.7'
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function sortReviews(items: AlbumReviewItem[], field: SortField, dir: SortDir): AlbumReviewItem[] {
  return [...items].sort((a, b) => {
    let av: string | number = ''
    let bv: string | number = ''
    switch (field) {
      case 'username': av = a.username;   bv = b.username;   break
      case 'date':     av = a.reviewed_at; bv = b.reviewed_at; break
      case 'rating':   av = a.rating ?? 0; bv = b.rating ?? 0; break
    }
    if (typeof av === 'number' && typeof bv === 'number') {
      return dir === 'asc' ? av - bv : bv - av
    }
    return dir === 'asc'
      ? String(av).localeCompare(String(bv))
      : String(bv).localeCompare(String(av))
  })
}

// ==================== SORT BUTTON ====================

interface SortButtonProps {
  field: SortField
  label: string
  active: SortField
  dir: SortDir
  onClick: (f: SortField) => void
}

function SortButton({ field, label, active, dir, onClick }: SortButtonProps) {
  const Icon = active !== field ? IconSelector : dir === 'asc' ? IconChevronUp : IconChevronDown
  return (
    <UnstyledButton
      onClick={() => onClick(field)}
      style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}
      c="dimmed"
    >
      {label}
      <Icon size={13} />
    </UnstyledButton>
  )
}

// ==================== REVIEW ROW ====================

interface ReviewRowProps {
  item: AlbumReviewItem
  isExpanded: boolean
  onToggle: () => void
}

function ReviewRow({ item, isExpanded, onToggle }: ReviewRowProps) {
  return (
    <>
      <Table.Tr style={{ cursor: 'pointer' }} onClick={onToggle}>
        <Table.Td>
          <Text size="sm" fw={500}>{item.username}</Text>
        </Table.Td>
        <Table.Td>
          <Text size="sm" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
            {formatDate(item.reviewed_at)}
          </Text>
        </Table.Td>
        <Table.Td>
          <Text size="sm" fw={700} c={item.rating !== null ? ratingColor(item.rating) : 'dimmed'}>
            {item.rating ?? '—'}
          </Text>
        </Table.Td>
        <Table.Td>
          {isExpanded ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
        </Table.Td>
      </Table.Tr>

      {isExpanded && (
        <Table.Tr>
          <Table.Td
            colSpan={4}
            style={{ background: 'var(--mantine-color-dark-7)', padding: '12px 20px' }}
          >
            <Text
              size="sm"
              c={item.comment ? undefined : 'dimmed'}
              fs={item.comment ? 'italic' : undefined}
              style={{ whiteSpace: 'pre-wrap' }}
            >
              {item.comment ? `"${item.comment}"` : 'No notes left.'}
            </Text>
          </Table.Td>
        </Table.Tr>
      )}
    </>
  )
}

// ==================== MAIN PAGE ====================

export default function AlbumPage() {
  const { albumId: albumIdStr } = useParams<{ albumId: string }>()
  const albumId = Number(albumIdStr)

  const [sortField, setSortField] = useState<SortField>('date')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const { data: album, isLoading: albumLoading } = useAlbumDetails(albumId)
  const { data: reviews = [], isLoading: reviewsLoading } = useAlbumReviews(albumId)
  const { data: stats, isLoading: statsLoading } = useAlbumStats(albumId)
  const { data: myStats } = useMyStats()
  const hasSpotify = myStats?.has_spotify ?? false

  const sortedReviews = useMemo(
    () => sortReviews(reviews, sortField, sortDir),
    [reviews, sortField, sortDir],
  )

  const toggleSort = (field: SortField) => {
    if (sortField === field) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else { setSortField(field); setSortDir('asc') }
  }

  const releaseYear = album?.release_date ? album.release_date.slice(0, 4) : null

  return (
    <AppShell>
      <Stack gap="lg">

        {/* ── ALBUM HEADER ── */}
        <Group gap="lg" align="flex-start" wrap="nowrap">
          {albumLoading ? (
            <Skeleton w={120} h={120} radius="sm" style={{ flexShrink: 0 }} />
          ) : album?.cover_url ? (
            <img
              src={album.cover_url}
              width={120}
              height={120}
              style={{ borderRadius: 8, flexShrink: 0, objectFit: 'cover' }}
            />
          ) : (
            <div
              style={{
                width: 120,
                height: 120,
                background: 'var(--mantine-color-dark-5)',
                borderRadius: 8,
                flexShrink: 0,
              }}
            />
          )}

          <Stack gap={4} style={{ minWidth: 0 }}>
            {albumLoading ? (
              <>
                <Skeleton h={28} w={240} />
                <Skeleton h={18} w={160} mt={4} />
                <Skeleton h={16} w={100} mt={4} />
              </>
            ) : (
              <>
                <Title order={2} lineClamp={2}>{album?.title}</Title>
                <Text size="lg" c="dimmed">{album?.artist}</Text>
                <Group gap="xs" mt={4}>
                  {releaseYear && (
                    <Text size="sm" c="dimmed">{releaseYear}</Text>
                  )}
                  {album?.genres.map((g) => (
                    <Badge key={g} size="xs" variant="light" color="violet">{g}</Badge>
                  ))}
                </Group>
              </>
            )}
          </Stack>
        </Group>

        {/* ── SPOTIFY PLAYER ── */}
        {albumLoading ? (
          <Skeleton h={180} radius="md" />
        ) : album?.spotify_album_id ? (
          <SpotifyPlayer spotifyAlbumId={album.spotify_album_id} hasSpotify={hasSpotify} />
        ) : null}

        {/* ── GLOBAL RATING + HISTOGRAM ── */}
        <Paper withBorder p="md" radius="md">
          {statsLoading ? (
            <Skeleton h={140} />
          ) : (
            <Stack gap="sm">
              <Group gap="xl" align="flex-end">
                <Stack gap={2}>
                  <Text size="xs" c="dimmed" tt="uppercase" fw={600} style={{ letterSpacing: 1 }}>
                    Global Rating
                  </Text>
                  <Text
                    size="xl"
                    fw={700}
                    style={{ fontSize: 40, lineHeight: 1 }}
                    c={stats?.average_rating !== null && stats?.average_rating !== undefined
                      ? ratingColor(stats.average_rating)
                      : 'dimmed'}
                  >
                    {stats?.average_rating !== null && stats?.average_rating !== undefined
                      ? stats.average_rating.toFixed(1)
                      : '—'}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {stats?.review_count ?? 0} review{stats?.review_count !== 1 ? 's' : ''}
                  </Text>
                </Stack>

                <Box style={{ flex: 1, minWidth: 0 }}>
                  <ResponsiveContainer width="100%" height={100}>
                    <BarChart data={stats?.histogram ?? []} barCategoryGap="10%" margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--mantine-color-dark-4)" vertical={false} />
                      <XAxis
                        dataKey="bucket_start"
                        tick={{ fontSize: 10, fill: 'var(--mantine-color-dimmed)' }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        allowDecimals={false}
                        tick={{ fontSize: 10, fill: 'var(--mantine-color-dimmed)' }}
                        axisLine={false}
                        tickLine={false}
                        width={20}
                      />
                      <RechartsTooltip
                        formatter={(value, _, props) => [
                          `${value} review${value !== 1 ? 's' : ''}`,
                          `${props.payload.bucket_start}–${props.payload.bucket_end}`,
                        ]}
                        contentStyle={{
                          background: 'var(--mantine-color-dark-7)',
                          border: '1px solid var(--mantine-color-dark-4)',
                          borderRadius: 4,
                          fontSize: 12,
                        }}
                        labelStyle={{ display: 'none' }}
                        itemStyle={{ color: '#c1c2c5' }}
                        cursor={{ fill: 'var(--mantine-color-dark-5)' }}
                      />
                      <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                        {(stats?.histogram ?? []).map((bucket) => (
                          <Cell
                            key={bucket.bucket_start}
                            fill={
                              bucket.bucket_start < 3 ? 'var(--mantine-color-red-7)' :
                              bucket.bucket_start < 5 ? '#6b4226' :
                              bucket.bucket_start < 7 ? 'var(--mantine-color-orange-5)' :
                              bucket.bucket_start < 9 ? 'var(--mantine-color-lime-5)' :
                              'var(--mantine-color-green-7)'
                            }
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </Box>
              </Group>
            </Stack>
          )}
        </Paper>

        {/* ── REVIEWS TABLE ── */}
        <Stack gap="sm">
          <Text fw={600} size="sm">
            {reviewsLoading ? (
              <Skeleton h={16} w={80} display="inline-block" />
            ) : (
              `${reviews.length} review${reviews.length !== 1 ? 's' : ''}`
            )}
          </Text>

          {reviewsLoading ? (
            <Stack gap="xs">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} h={48} radius="sm" />
              ))}
            </Stack>
          ) : !reviews.length ? (
            <Text c="dimmed" size="sm">No reviews yet.</Text>
          ) : (
            <ScrollArea>
              <Table highlightOnHover verticalSpacing="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>
                      <SortButton field="username" label="Reviewer" active={sortField} dir={sortDir} onClick={toggleSort} />
                    </Table.Th>
                    <Table.Th>
                      <SortButton field="date" label="Date" active={sortField} dir={sortDir} onClick={toggleSort} />
                    </Table.Th>
                    <Table.Th>
                      <SortButton field="rating" label="Rating" active={sortField} dir={sortDir} onClick={toggleSort} />
                    </Table.Th>
                    <Table.Th w={28} />
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {sortedReviews.map((item) => (
                    <ReviewRow
                      key={item.id}
                      item={item}
                      isExpanded={expandedId === item.id}
                      onToggle={() =>
                        setExpandedId((prev) => (prev === item.id ? null : item.id))
                      }
                    />
                  ))}
                </Table.Tbody>
              </Table>
            </ScrollArea>
          )}
        </Stack>

      </Stack>
    </AppShell>
  )
}
