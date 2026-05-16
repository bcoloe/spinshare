import { useEffect, useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ActionIcon,
  Anchor,
  Badge,
  Box,
  Button,
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
  IconBrandApple,
  IconBrandSpotify,
  IconBrandYoutube,
  IconChevronDown,
  IconChevronRight,
  IconChevronUp,
  IconExternalLink,
  IconHeart,
  IconHeartFilled,
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
import PlaylistPickerModal, { type PickablePlaylist } from '../components/spin/PlaylistPickerModal'
import ReviewForm from '../components/spin/ReviewForm'
import { usePlayer } from '../context/PlayerContext'
import { useMyReview } from '../hooks/useDailySpin'
import { useAlbumDetails, useAlbumReviews, useAlbumStats } from '../hooks/useAlbumPage'
import { getSpotifyToken, getAppleMusicDeveloperToken } from '../services/streamingService'
import {
  fetchUserPlaylists,
  fetchAlbumTracks,
  addTracksToPlaylist,
  removeTracksFromPlaylist,
  getPlaylistsContainingUris,
} from '../services/spotifyApiClient'
import {
  fetchAppleMusicAlbumTracks,
  fetchAppleMusicUserPlaylists,
  addSongsToAppleMusicPlaylist,
} from '../services/appleMusicApiClient'
import type { UnifiedTrack } from '../context/PlayerContext'
import type { AlbumReviewItem } from '../types/album'

// ==================== TYPES ====================

type SortField = 'username' | 'date' | 'rating'
type SortDir = 'asc' | 'desc'

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

// ==================== ALBUM TRACKLIST ====================

interface AlbumTracklistProps {
  appAlbumId: number
  spotifyAlbumId: string
  appleMusicAlbumId: string | null | undefined
  albumTitle: string
  albumArtist: string
  albumCoverUrl: string | null
  effectivePlayService: 'spotify' | 'apple_music'
}

function AlbumTracklist({
  appAlbumId,
  spotifyAlbumId,
  appleMusicAlbumId,
  albumTitle,
  albumArtist,
  albumCoverUrl,
  effectivePlayService,
}: AlbumTracklistProps) {
  const {
    tracks: contextTracks,
    tracksLoading: contextTracksLoading,
    skipToTrack,
    albumSaved,
    albumSavePending,
    toggleAlbumSave,
    canRemoveFromLibrary,
    currentTrackUri,
    currentTrackNumber,
    appleMusicUserToken,
    playingAlbumMeta,
    startAlbum,
    playInAppleMusic,
  } = usePlayer()

  const isAppleMusic = effectivePlayService === 'apple_music'
  const accentColor = isAppleMusic ? '#fc3c44' : '#1DB954'
  const isThisAlbumPlaying = playingAlbumMeta?.appAlbumId === appAlbumId

  // Pre-play local tracks — fetched from the service API before any playback starts
  const [localTracks, setLocalTracks] = useState<UnifiedTrack[]>([])
  const [localTracksLoading, setLocalTracksLoading] = useState(false)

  useEffect(() => {
    if (isThisAlbumPlaying) return
    let cancelled = false
    setLocalTracksLoading(true)
    ;(async () => {
      try {
        if (isAppleMusic && appleMusicAlbumId) {
          const devToken = await getAppleMusicDeveloperToken()
          const t = await fetchAppleMusicAlbumTracks(devToken, appleMusicAlbumId)
          if (!cancelled) setLocalTracks(t)
        } else {
          const token = await getSpotifyToken()
          const t = await fetchAlbumTracks(token, spotifyAlbumId)
          if (!cancelled) setLocalTracks(t.map((track) => ({
            id: track.uri,
            name: track.name,
            trackNumber: track.trackNumber,
            durationMs: track.durationMs,
            artist: track.artists,
          })))
        }
      } catch {} finally {
        if (!cancelled) setLocalTracksLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [isThisAlbumPlaying, isAppleMusic, appleMusicAlbumId, spotifyAlbumId])

  const displayTracks = isThisAlbumPlaying ? contextTracks : localTracks
  const displayTracksLoading = isThisAlbumPlaying ? contextTracksLoading : localTracksLoading

  const [pickerScope, setPickerScope] = useState<'album' | 'track'>('album')
  const [selectedTrackId, setSelectedTrackId] = useState<string | null>(null)
  const [pickerOpened, { open: openPicker, close: closePicker }] = useDisclosure(false)

  const openAlbumPicker = () => { setPickerScope('album'); openPicker() }
  const openTrackPicker = (trackId: string) => { setSelectedTrackId(trackId); setPickerScope('track'); openPicker() }

  const pickerTrackIds = pickerScope === 'album'
    ? displayTracks.map((t) => t.id)
    : selectedTrackId ? [selectedTrackId] : []

  const fetchPlaylists = async (): Promise<PickablePlaylist[]> => {
    if (isAppleMusic) {
      if (!appleMusicUserToken) throw new Error('Apple Music not authorized')
      const devToken = await getAppleMusicDeveloperToken()
      return fetchAppleMusicUserPlaylists(devToken, appleMusicUserToken)
    }
    const token = await getSpotifyToken()
    const pls = await fetchUserPlaylists(token)
    return pls.map((p) => ({ id: p.id, name: p.name, imageUrl: p.imageUrl ?? null }))
  }

  const checkContaining = isAppleMusic
    ? undefined
    : async (pls: PickablePlaylist[]) => {
        const token = await getSpotifyToken()
        const spotifyPls = pls.map((p) => ({ id: p.id, name: p.name, imageUrl: p.imageUrl ?? '' }))
        return getPlaylistsContainingUris(token, spotifyPls, pickerTrackIds)
      }

  const onAdd = async (playlistId: string) => {
    if (isAppleMusic) {
      if (!appleMusicUserToken) throw new Error('Apple Music not authorized')
      const devToken = await getAppleMusicDeveloperToken()
      await addSongsToAppleMusicPlaylist(playlistId, pickerTrackIds, devToken, appleMusicUserToken)
      return
    }
    const token = await getSpotifyToken()
    await addTracksToPlaylist(token, playlistId, pickerTrackIds)
  }

  const onRemove = isAppleMusic
    ? undefined
    : async (playlistId: string) => {
        const token = await getSpotifyToken()
        await removeTracksFromPlaylist(token, playlistId, pickerTrackIds)
      }

  const handleToggleSave = async () => {
    if (!isThisAlbumPlaying) return  // save only works when playing (context handles the album state)
    try {
      await toggleAlbumSave()
      if (isAppleMusic) {
        notifications.show({ color: 'green', message: 'Saved to Apple Music Library' })
      } else {
        notifications.show({
          color: albumSaved ? undefined : 'green',
          message: albumSaved ? 'Removed from Your Library' : 'Saved to Your Library',
        })
      }
    } catch (err) {
      notifications.show({ color: 'red', message: err instanceof Error ? err.message : 'Could not update library' })
    }
  }

  const handleTrackClick = (track: UnifiedTrack, index: number) => {
    if (isThisAlbumPlaying) {
      skipToTrack(index)
      return
    }
    const meta = {
      spotifyAlbumId,
      appleMusicAlbumId,
      title: albumTitle,
      artist: albumArtist,
      coverUrl: albumCoverUrl,
      appAlbumId,
    }
    if (isAppleMusic) {
      playInAppleMusic(meta)
    } else {
      startAlbum(spotifyAlbumId, meta, track.id)
    }
  }

  const saveLabel = isAppleMusic
    ? 'Save to Library'
    : albumSaved && canRemoveFromLibrary ? 'Remove from library' : 'Save album'

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
          <Tooltip label={isThisAlbumPlaying ? saveLabel : 'Play to enable library save'} withArrow>
            <ActionIcon
              variant="subtle"
              size="sm"
              color={isThisAlbumPlaying && albumSaved && canRemoveFromLibrary ? 'green' : 'gray'}
              loading={albumSavePending}
              disabled={!isThisAlbumPlaying}
              onClick={handleToggleSave}
            >
              {isThisAlbumPlaying && albumSaved && canRemoveFromLibrary
                ? <IconHeartFilled size={14} color="var(--mantine-color-green-5)" />
                : <IconHeart size={14} />}
            </ActionIcon>
          </Tooltip>
          <Tooltip label="Add album to playlist" withArrow>
            <ActionIcon variant="subtle" size="sm" onClick={openAlbumPicker} disabled={displayTracks.length === 0}>
              <IconPlaylistAdd size={14} />
            </ActionIcon>
          </Tooltip>
        </Group>

        <ScrollArea h={280} type="hover">
          {displayTracksLoading
            ? Array.from({ length: 6 }).map((_, i) => (
                <Box key={i} px="sm" py={6}>
                  <Skeleton h={14} radius="sm" />
                </Box>
              ))
            : displayTracks.map((track, index) => {
                const isActive = isThisAlbumPlaying && (isAppleMusic
                  ? currentTrackNumber === track.trackNumber
                  : track.id === currentTrackUri)
                return (
                  <Group
                    key={track.id}
                    px="sm"
                    py={7}
                    gap="xs"
                    wrap="nowrap"
                    style={(theme) => ({
                      cursor: 'pointer',
                      background: isActive ? theme.colors.dark[5] : 'transparent',
                      borderLeft: isActive ? `2px solid ${accentColor}` : '2px solid transparent',
                    })}
                    onClick={() => handleTrackClick(track, index)}
                  >
                    <Text size="xs" c="dimmed" w={20} ta="right" style={{ flexShrink: 0 }}>
                      {isActive
                        ? (isAppleMusic
                            ? <IconBrandApple size={12} color="#fc3c44" />
                            : <IconBrandSpotify size={12} color="#1DB954" />)
                        : track.trackNumber}
                    </Text>
                    <Stack gap={0} style={{ flex: 1, minWidth: 0 }}>
                      <Text size="sm" c={isActive ? (isAppleMusic ? 'red.4' : 'green.4') : undefined} fw={isActive ? 500 : 400} lineClamp={1}>
                        {track.name}
                      </Text>
                      <Text size="xs" c="dimmed" lineClamp={1}>{track.artist}</Text>
                    </Stack>
                    <Text size="xs" c="dimmed" style={{ flexShrink: 0 }}>
                      {formatTrackDuration(track.durationMs)}
                    </Text>
                    <Tooltip label="Add to playlist" withArrow>
                      <ActionIcon
                        variant="subtle"
                        size="xs"
                        style={{ flexShrink: 0 }}
                        onClick={(e) => { e.stopPropagation(); openTrackPicker(track.id) }}
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
        title={pickerScope === 'album' ? 'Add album to playlist' : 'Add track to playlist'}
        fetchPlaylists={fetchPlaylists}
        checkContaining={checkContaining}
        onAdd={onAdd}
        onRemove={onRemove}
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
  const { data: myReview = null, isLoading: myReviewLoading } = useMyReview(albumId)

  const {
    status: playerStatus,
    hasSpotify,
    hasAppleMusic,
    preferredService,
    playingSpotifyAlbumId,
    playingAppleMusicAlbumId,
    startAlbum,
    playInAppleMusic,
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
        ) : album?.spotify_album_id ? (() => {
          const canPlaySpotify = hasSpotify
          const canPlayAppleMusic = hasAppleMusic && !!album.apple_music_album_id
          // Determine which service will handle the embedded play button
          const effectivePlayService: 'spotify' | 'apple_music' = (() => {
            if (preferredService === 'apple_music' && canPlayAppleMusic) return 'apple_music'
            if (preferredService === 'spotify' && canPlaySpotify) return 'spotify'
            if (canPlaySpotify) return 'spotify'
            if (canPlayAppleMusic) return 'apple_music'
            return preferredService
          })()
          const canPlay = effectivePlayService === 'apple_music' ? canPlayAppleMusic : canPlaySpotify
          const playMeta = {
            spotifyAlbumId: album.spotify_album_id!,
            appleMusicAlbumId: album.apple_music_album_id,
            title: album.title,
            artist: album.artist,
            coverUrl: album.cover_url ?? null,
            appAlbumId: album.id,
          }
          const handlePlay = () => effectivePlayService === 'apple_music'
            ? playInAppleMusic(playMeta)
            : startAlbum(album.spotify_album_id!, playMeta)
          return (
            <Stack gap="sm">
              <Group gap="sm" wrap="wrap">
                <Button
                  variant="filled"
                  color={effectivePlayService === 'apple_music' ? 'red' : 'green'}
                  size="sm"
                  leftSection={effectivePlayService === 'apple_music'
                    ? <IconBrandApple size={16} />
                    : <IconBrandSpotify size={16} />}
                  loading={playerStatus === 'loading'}
                  disabled={!canPlay}
                  onClick={handlePlay}
                >
                  Play
                </Button>
                <Button
                  component="a"
                  href={`spotify:album:${album.spotify_album_id}`}
                  variant="light"
                  color="green"
                  size="sm"
                  leftSection={<IconBrandSpotify size={16} />}
                >
                  Open in Spotify
                </Button>
                <Button
                  component="a"
                  href={`https://open.spotify.com/album/${album.spotify_album_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  variant="subtle"
                  size="sm"
                  leftSection={<IconExternalLink size={16} />}
                >
                  Web Player
                </Button>
                {album.youtube_music_id && (
                  <Button
                    component="a"
                    href={`https://music.youtube.com/browse/${album.youtube_music_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    variant="subtle"
                    size="sm"
                    leftSection={<IconBrandYoutube size={16} />}
                  >
                    YouTube Music
                  </Button>
                )}
                {album.apple_music_album_id && (
                  <>
                    <Button
                      component="a"
                      href={`https://music.apple.com/album/${album.apple_music_album_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      variant="light"
                      color="red"
                      size="sm"
                      leftSection={<IconBrandApple size={16} />}
                    >
                      Open in Apple Music
                    </Button>
                  </>
                )}
                {(playingSpotifyAlbumId === album.spotify_album_id || playingAppleMusicAlbumId === album.apple_music_album_id) && (playerStatus === 'playing' || playerStatus === 'paused') && (
                  <Badge color="green" variant="light" leftSection={<IconMusic size={10} />}>
                    {playerStatus === 'playing' ? 'Now Playing' : 'Paused'}
                  </Badge>
                )}
              </Group>
              {!hasSpotify && !hasAppleMusic && (
                <Text size="xs" c="dimmed">
                  <Anchor component={Link} to="/profile" size="xs">Connect Spotify or Apple Music</Anchor> on your profile to enable the embedded player
                </Text>
              )}
              {canPlay && (
                <AlbumTracklist
                  appAlbumId={album.id}
                  spotifyAlbumId={album.spotify_album_id}
                  appleMusicAlbumId={album.apple_music_album_id}
                  albumTitle={album.title}
                  albumArtist={album.artist}
                  albumCoverUrl={album.cover_url ?? null}
                  effectivePlayService={effectivePlayService}
                />
              )}
            </Stack>
          )
        })() : null}

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

        {/* ── YOUR REVIEW ── */}
        <Paper withBorder p="md" radius="md">
          {myReviewLoading ? (
            <Skeleton h={80} />
          ) : (
            <ReviewForm key={albumId} albumId={albumId} existingReview={myReview} />
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
