import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  ActionIcon,
  Anchor,
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
  Tooltip,
  UnstyledButton,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import {
  IconBrandSpotify,
  IconChevronDown,
  IconChevronRight,
  IconChevronUp,
  IconExternalLink,
  IconMusic,
  IconPlaylistAdd,
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
import PlaylistPickerModal from '../components/spin/PlaylistPickerModal'
import { usePlayer } from '../context/PlayerContext'
import { useAlbumDetails, useAlbumReviews, useAlbumStats } from '../hooks/useAlbumPage'
import { getSpotifyToken } from '../services/streamingService'
import { isAlbumSaved, saveAlbum, unsaveAlbum } from '../services/spotifyApiClient'
import type { AlbumReviewItem } from '../types/album'

// ==================== TYPES ====================

type SortField = 'username' | 'date' | 'rating'
type SortDir = 'asc' | 'desc'

interface AlbumTrack {
  uri: string
  name: string
  trackNumber: number
  durationMs: number
  artists: string
}

// ==================== HELPERS ====================

function formatTrackDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  return `${min}:${sec.toString().padStart(2, '0')}`
}

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

// ==================== IFRAME FALLBACK ====================

function IframeFallback({ spotifyAlbumId }: { spotifyAlbumId: string }) {
  return (
    <Stack gap="xs">
      <iframe
        src={`https://open.spotify.com/embed/album/${spotifyAlbumId}?utm_source=generator&theme=0`}
        width="100%"
        height="352"
        frameBorder={0}
        allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
        loading="lazy"
        style={{ borderRadius: 12 }}
      />
      <Anchor
        href={`https://open.spotify.com/album/${spotifyAlbumId}`}
        target="_blank"
        rel="noopener noreferrer"
        size="sm"
        c="dimmed"
      >
        <Group gap={4}>
          <IconExternalLink size={14} />
          Open in Spotify
        </Group>
      </Anchor>
    </Stack>
  )
}

// ==================== ALBUM TRACKLIST ====================

interface AlbumTracklistProps {
  spotifyAlbumId: string
  albumTitle: string
  albumArtist: string
  albumCoverUrl: string | null
  appAlbumId: number
}

function AlbumTracklist({ spotifyAlbumId, albumTitle, albumArtist, albumCoverUrl, appAlbumId }: AlbumTracklistProps) {
  const { currentTrackUri, startAlbum } = usePlayer()
  const [tracks, setTracks] = useState<AlbumTrack[]>([])
  const [tracksLoading, setTracksLoading] = useState(false)
  const [albumSaved, setAlbumSaved] = useState(false)
  const [savingAlbum, setSavingAlbum] = useState(false)
  const [pickerUris, setPickerUris] = useState<string[]>([])
  const [pickerTitle, setPickerTitle] = useState('Add to playlist')
  const [pickerOpened, { open: openPicker, close: closePicker }] = useDisclosure(false)
  const activeTrackRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    setTracks([])
    setAlbumSaved(false)
  }, [spotifyAlbumId])

  useEffect(() => {
    if (tracks.length > 0) return
    let cancelled = false
    setTracksLoading(true)
    async function fetchTracks() {
      try {
        const token = await getSpotifyToken()
        const resp = await fetch(
          `https://api.spotify.com/v1/albums/${spotifyAlbumId}/tracks?limit=50`,
          { headers: { Authorization: `Bearer ${token}` } },
        )
        if (!resp.ok || cancelled) return
        const data = await resp.json()
        setTracks(
          data.items.map((t: { uri: string; name: string; track_number: number; duration_ms: number; artists: Array<{ name: string }> }) => ({
            uri: t.uri,
            name: t.name,
            trackNumber: t.track_number,
            durationMs: t.duration_ms,
            artists: t.artists.map((a) => a.name).join(', '),
          })),
        )
      } finally {
        if (!cancelled) setTracksLoading(false)
      }
    }
    fetchTracks()
    return () => { cancelled = true }
  }, [spotifyAlbumId, tracks.length])

  useEffect(() => {
    if (tracks.length === 0) return
    getSpotifyToken()
      .then((token) => isAlbumSaved(token, spotifyAlbumId))
      .then(setAlbumSaved)
      .catch(() => {})
  }, [tracks.length, spotifyAlbumId])

  useEffect(() => {
    activeTrackRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [currentTrackUri])

  const albumMeta = { spotifyAlbumId, title: albumTitle, artist: albumArtist, coverUrl: albumCoverUrl, appAlbumId }

  const handleToggleSaveAlbum = async () => {
    setSavingAlbum(true)
    try {
      const token = await getSpotifyToken()
      if (albumSaved) {
        await unsaveAlbum(token, spotifyAlbumId)
        setAlbumSaved(false)
        notifications.show({ message: 'Removed from Your Library' })
      } else {
        await saveAlbum(token, spotifyAlbumId)
        setAlbumSaved(true)
        notifications.show({ color: 'green', message: 'Saved to Your Library' })
      }
    } catch (err) {
      notifications.show({ color: 'red', message: err instanceof Error ? err.message : 'Could not update library' })
    } finally {
      setSavingAlbum(false)
    }
  }

  const handleOpenPicker = (target: 'album' | string) => {
    setPickerUris(target === 'album' ? tracks.map((t) => t.uri) : [target])
    setPickerTitle(target === 'album' ? 'Add album to playlist' : 'Add track to playlist')
    openPicker()
  }

  return (
    <>
      <Box
        style={(theme) => ({
          background: theme.colors.dark[7],
          borderRadius: theme.radius.md,
          border: `1px solid ${theme.colors.dark[4]}`,
          overflow: 'hidden',
        })}
      >
        {/* Album-level actions */}
        <Group px="sm" py="xs" gap="xs" style={(theme) => ({ borderBottom: `1px solid ${theme.colors.dark[5]}` })}>
          <Text size="xs" c="dimmed" style={{ flex: 1 }}>Tracks</Text>
          <Tooltip label={albumSaved ? 'Remove from library' : 'Save album'} withArrow>
            <ActionIcon
              variant="subtle"
              size="sm"
              color={albumSaved ? 'green' : 'gray'}
              loading={savingAlbum}
              onClick={handleToggleSaveAlbum}
            >
              {albumSaved
                ? <IconMusic size={14} color="var(--mantine-color-green-5)" />
                : <IconMusic size={14} />}
            </ActionIcon>
          </Tooltip>
          <Tooltip label="Add album to playlist" withArrow>
            <ActionIcon variant="subtle" size="sm" onClick={() => handleOpenPicker('album')} disabled={tracks.length === 0}>
              <IconPlaylistAdd size={14} />
            </ActionIcon>
          </Tooltip>
        </Group>

        <ScrollArea h={280} type="hover">
          {tracksLoading
            ? Array.from({ length: 6 }).map((_, i) => (
                <Box key={i} px="sm" py={6}>
                  <Skeleton h={14} radius="sm" />
                </Box>
              ))
            : tracks.map((track) => {
                const isActive = track.uri === currentTrackUri
                return (
                  <Group
                    key={track.uri}
                    ref={isActive ? activeTrackRef : null}
                    px="sm"
                    py={7}
                    gap="xs"
                    wrap="nowrap"
                    style={(theme) => ({
                      cursor: 'pointer',
                      background: isActive ? theme.colors.dark[5] : 'transparent',
                      borderLeft: isActive ? '2px solid #1DB954' : '2px solid transparent',
                    })}
                    onClick={() => startAlbum(spotifyAlbumId, albumMeta, track.uri)}
                  >
                    <Text size="xs" c="dimmed" w={20} ta="right" style={{ flexShrink: 0 }}>
                      {isActive ? <IconBrandSpotify size={12} color="#1DB954" /> : track.trackNumber}
                    </Text>
                    <Stack gap={0} style={{ flex: 1, minWidth: 0 }}>
                      <Text size="sm" c={isActive ? 'green.4' : undefined} fw={isActive ? 500 : 400} lineClamp={1}>
                        {track.name}
                      </Text>
                      <Text size="xs" c="dimmed" lineClamp={1}>{track.artists}</Text>
                    </Stack>
                    <Text size="xs" c="dimmed" style={{ flexShrink: 0 }}>
                      {formatTrackDuration(track.durationMs)}
                    </Text>
                    <Tooltip label="Add to playlist" withArrow>
                      <ActionIcon
                        variant="subtle"
                        size="xs"
                        style={{ flexShrink: 0 }}
                        onClick={(e) => { e.stopPropagation(); handleOpenPicker(track.uri) }}
                      >
                        <IconPlaylistAdd size={12} />
                      </ActionIcon>
                    </Tooltip>
                  </Group>
                )
              })}
        </ScrollArea>
      </Box>

      <PlaylistPickerModal
        opened={pickerOpened}
        onClose={closePicker}
        uris={pickerUris}
        title={pickerTitle}
      />
    </>
  )
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

  const {
    status: playerStatus,
    hasSpotify,
    playingSpotifyAlbumId,
    startAlbum,
  } = usePlayer()

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

        {/* ── PLAYER SECTION ── */}
        {albumLoading ? (
          <Skeleton h={48} radius="md" />
        ) : album?.spotify_album_id ? (
          !hasSpotify ? (
            <IframeFallback spotifyAlbumId={album.spotify_album_id} />
          ) : (
            <Stack gap="sm">
              <Group gap="sm">
                <ActionIcon
                  variant="filled"
                  color="green"
                  radius="xl"
                  size="lg"
                  loading={playerStatus === 'loading'}
                  onClick={() => startAlbum(
                    album.spotify_album_id!,
                    {
                      spotifyAlbumId: album.spotify_album_id!,
                      title: album.title,
                      artist: album.artist,
                      coverUrl: album.cover_url ?? null,
                      appAlbumId: album.id,
                    },
                  )}
                  aria-label="Play in player"
                >
                  <IconBrandSpotify size={18} />
                </ActionIcon>
                <Text size="sm" c="dimmed">Play in Player</Text>
                {playingSpotifyAlbumId === album.spotify_album_id && (playerStatus === 'playing' || playerStatus === 'paused') && (
                  <Badge color="green" variant="light" leftSection={<IconMusic size={10} />}>
                    {playerStatus === 'playing' ? 'Now Playing' : 'Paused'}
                  </Badge>
                )}
              </Group>
              {(playerStatus === 'ready' || playerStatus === 'playing' || playerStatus === 'paused') && (
                <AlbumTracklist
                  spotifyAlbumId={album.spotify_album_id}
                  albumTitle={album.title}
                  albumArtist={album.artist}
                  albumCoverUrl={album.cover_url ?? null}
                  appAlbumId={album.id}
                />
              )}
            </Stack>
          )
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
