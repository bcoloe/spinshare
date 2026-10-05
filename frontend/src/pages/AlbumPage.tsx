import { useEffect, useState } from 'react'
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
  Text,
  Title,
  Tooltip,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import {
  IconBrandApple,
  IconBrandSpotify,
  IconBrandWikipedia,
  IconBrandYoutube,
  IconExternalLink,
  IconHeart,
  IconHeartFilled,
  IconMusic,
  IconPlaylistAdd,
} from '@tabler/icons-react'
import AppShell from '../components/layout/AppShell'
import AlbumRatingSummary from '../components/albums/AlbumRatingSummary'
import AlbumReviewsTable from '../components/albums/AlbumReviewsTable'
import LinkRepairControl from '../components/albums/LinkRepairControl'
import NominationBadge from '../components/albums/NominationBadge'
import PlaylistPickerModal, { type PickablePlaylist } from '../components/spin/PlaylistPickerModal'
import ReviewForm from '../components/spin/ReviewForm'
import GuestReviewPrompt from '../components/spin/GuestReviewPrompt'
import { usePlayer } from '../context/PlayerContext'
import { useAuth } from '../hooks/useAuth'
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

// ==================== HELPERS ====================

function formatTrackDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  return `${min}:${sec.toString().padStart(2, '0')}`
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

// ==================== MAIN PAGE ====================

export default function AlbumPage() {
  const { albumId: albumIdStr } = useParams<{ albumId: string }>()
  const albumId = Number(albumIdStr)
  const { user } = useAuth()
  // Keyed by album so walking to the next album re-arms both guards without an
  // effect — this component is reused across /albums/:albumId, not remounted.
  const [scoreRevealedFor, setScoreRevealedFor] = useState<number | null>(null)
  const [reviewsRevealedFor, setReviewsRevealedFor] = useState<number | null>(null)

  const { data: album, isLoading: albumLoading } = useAlbumDetails(albumId)
  const { data: reviews = [], isLoading: reviewsLoading } = useAlbumReviews(albumId)
  const { data: stats, isLoading: statsLoading } = useAlbumStats(albumId)
  const { data: myReview = null, isLoading: myReviewLoading } = useMyReview(albumId, !!user)

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

  /**
   * Other people's opinions stay behind a blur until this viewer has published
   * their own review, so the group's verdict cannot anchor theirs.
   *
   * A draft does not count — it is invisible to everyone else, so its author
   * has not yet put anything on the line. Signed-out visitors have no review
   * to anchor and see the page as they always have.
   *
   * Both sections stay on their skeletons until the viewer's own review has
   * loaded, because guessing either way shows the wrong thing for a moment: a
   * blur that lifts for someone who already reviewed, or a score that flashes
   * at someone who has not.
   */
  const hasPublishedReview = !!myReview && !myReview.is_draft
  const spoilerApplies = !!user && !hasPublishedReview

  /**
   * The two guards are armed separately, and each only when its own section has
   * something to give away: an album carrying a single unrated review has rows
   * worth sealing but no aggregate, and the score card would otherwise offer to
   * reveal a dash.
   */
  const scoreGuarded = spoilerApplies && (stats?.review_count ?? 0) > 0
  const reviewsGuarded = spoilerApplies && reviews.length > 0

  const scoreHidden = scoreGuarded && scoreRevealedFor !== albumId
  const reviewsHidden = reviewsGuarded && reviewsRevealedFor !== albumId

  const toggleScore = scoreGuarded
    ? () => setScoreRevealedFor((prev) => (prev === albumId ? null : albumId))
    : undefined
  const toggleReviews = reviewsGuarded
    ? () => setReviewsRevealedFor((prev) => (prev === albumId ? null : albumId))
    : undefined

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
                {album?.artist && (
                  <Anchor
                    component={Link}
                    to={`/artists/${encodeURIComponent(album.artist)}`}
                    size="lg"
                    c="dimmed"
                    style={{ width: 'fit-content' }}
                  >
                    {album.artist}
                  </Anchor>
                )}
                <Group gap="xs" mt={4}>
                  {releaseYear && (
                    <Text size="sm" c="dimmed">{releaseYear}</Text>
                  )}
                  {album?.genres.map((g) => (
                    <Badge key={g} size="xs" variant="light" color="violet">{g}</Badge>
                  ))}
                </Group>
                {stats && (
                  <Group gap="xs" mt={2}>
                    <NominationBadge total={stats.nomination_count} />
                  </Group>
                )}
              </>
            )}
          </Stack>
        </Group>

        {/* ── PLAYER SECTION ── */}
        {albumLoading ? (
          <Skeleton h={48} radius="md" />
        ) : album ? (() => {
          const spotifyId = album.spotify_album_id
          const appleMusicId = album.apple_music_album_id
          const canPlaySpotify = hasSpotify && !!spotifyId
          const canPlayAppleMusic = hasAppleMusic && !!appleMusicId
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
            spotifyAlbumId: spotifyId ?? '',
            appleMusicAlbumId: appleMusicId,
            title: album.title,
            artist: album.artist,
            coverUrl: album.cover_url ?? null,
            appAlbumId: album.id,
          }
          const handlePlay = () => {
            if (effectivePlayService === 'apple_music') return playInAppleMusic(playMeta)
            if (spotifyId) startAlbum(spotifyId, playMeta)
          }
          return (
            <Stack gap="sm">
              {/* Rendered for every album, not just Spotify-linked ones: a
                  service with no link keeps its slot as a disabled button, which
                  is what makes a missing link visible and reportable. Same
                  presentation as Today's Spin. */}
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
                <Tooltip label="Not found on Spotify" disabled={!!spotifyId}>
                  <Button
                    component="a"
                    href={spotifyId ? `spotify:album:${spotifyId}` : undefined}
                    variant="light"
                    color="green"
                    size="sm"
                    leftSection={<IconBrandSpotify size={16} />}
                    disabled={!spotifyId}
                  >
                    Open in Spotify
                  </Button>
                </Tooltip>
                <Tooltip label="Not found on Spotify" disabled={!!spotifyId}>
                  <Button
                    component="a"
                    href={spotifyId ? `https://open.spotify.com/album/${spotifyId}` : undefined}
                    target="_blank"
                    rel="noopener noreferrer"
                    variant="subtle"
                    size="sm"
                    leftSection={<IconExternalLink size={16} />}
                    disabled={!spotifyId}
                  >
                    Web Player
                  </Button>
                </Tooltip>
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
                {album.artist_url && (
                  <Button
                    component="a"
                    href={album.artist_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    variant="subtle"
                    size="sm"
                    leftSection={<IconExternalLink size={16} />}
                  >
                    Open URL
                  </Button>
                )}
                <Tooltip label="Not found on Apple Music" disabled={!!appleMusicId}>
                  <Button
                    component="a"
                    href={appleMusicId ? `https://music.apple.com/album/${appleMusicId}` : undefined}
                    target="_blank"
                    rel="noopener noreferrer"
                    variant="light"
                    color="red"
                    size="sm"
                    leftSection={<IconBrandApple size={16} />}
                    disabled={!appleMusicId}
                  >
                    Open in Apple Music
                  </Button>
                </Tooltip>
                <Tooltip label="No Wikipedia page found" disabled={!!album.wikipedia_url}>
                  <Button
                    component="a"
                    href={album.wikipedia_url ?? undefined}
                    target="_blank"
                    rel="noopener noreferrer"
                    variant="subtle"
                    size="sm"
                    leftSection={<IconBrandWikipedia size={16} />}
                    disabled={!album.wikipedia_url}
                  >
                    Wikipedia
                  </Button>
                </Tooltip>
                {/* Guarded on the id existing — two nulls would compare equal and
                    light this up on an album with no links at all. */}
                {((!!spotifyId && playingSpotifyAlbumId === spotifyId)
                  || (!!appleMusicId && playingAppleMusicAlbumId === appleMusicId))
                  && (playerStatus === 'playing' || playerStatus === 'paused') && (
                  <Badge color="green" variant="light" leftSection={<IconMusic size={10} />}>
                    {playerStatus === 'playing' ? 'Now Playing' : 'Paused'}
                  </Badge>
                )}
              </Group>
              <LinkRepairControl album={album} />
              {!hasSpotify && !hasAppleMusic && (
                <Text size="xs" c="dimmed">
                  <Anchor component={Link} to="/profile" size="xs">Connect Spotify or Apple Music</Anchor> on your profile to enable the embedded player
                </Text>
              )}
              {canPlay && (effectivePlayService === 'apple_music' ? !!appleMusicId : !!spotifyId) && (
                <AlbumTracklist
                  appAlbumId={album.id}
                  spotifyAlbumId={spotifyId ?? ''}
                  appleMusicAlbumId={appleMusicId}
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
        <AlbumRatingSummary
          stats={stats}
          loading={statsLoading || myReviewLoading}
          hidden={scoreHidden}
          onToggleHidden={toggleScore}
        />

        {/* ── YOUR REVIEW ── */}
        <Paper withBorder p="md" radius="md">
          {!user ? (
            <GuestReviewPrompt />
          ) : myReviewLoading ? (
            <Skeleton h={80} />
          ) : (
            <ReviewForm key={albumId} albumId={albumId} existingReview={myReview} />
          )}
        </Paper>

        {/* ── REVIEWS TABLE ── */}
        <AlbumReviewsTable
          reviews={reviews}
          loading={reviewsLoading || myReviewLoading}
          hidden={reviewsHidden}
          onToggleHidden={toggleReviews}
        />

      </Stack>
    </AppShell>
  )
}
