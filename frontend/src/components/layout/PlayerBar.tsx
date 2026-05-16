import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ActionIcon,
  Anchor,
  Divider,
  Group,
  Image,
  Menu,
  ScrollArea,
  Slider,
  Stack,
  Text,
  Tooltip,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import {
  IconBrandApple,
  IconBrandSpotify,
  IconChevronDown,
  IconChevronUp,
  IconDots,
  IconHeart,
  IconHeartFilled,
  IconMessageCircle,
  IconPlayerPauseFilled,
  IconPlayerPlayFilled,
  IconPlayerSkipBackFilled,
  IconPlayerSkipForwardFilled,
  IconPlaylistAdd,
  IconX,
} from '@tabler/icons-react'
import { usePlayer } from '../../context/PlayerContext'
import PlaylistPickerModal, { type PickablePlaylist } from '../spin/PlaylistPickerModal'
import { getSpotifyToken } from '../../services/streamingService'
import {
  fetchUserPlaylists,
  addTracksToPlaylist,
  removeTracksFromPlaylist,
  getPlaylistsContainingUris,
} from '../../services/spotifyApiClient'
import {
  fetchAppleMusicUserPlaylists,
  addSongsToAppleMusicPlaylist,
} from '../../services/appleMusicApiClient'
import { getAppleMusicDeveloperToken } from '../../services/streamingService'

function formatDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  return `${min}:${sec.toString().padStart(2, '0')}`
}

export default function PlayerBar() {
  const {
    status,
    currentTrackUri,
    currentTrackName,
    currentTrackNumber,
    position,
    duration,
    playingAlbumMeta,
    activeService,
    minimized,
    toggleMinimized,
    togglePlay,
    skipNext,
    skipPrevious,
    seekTo,
    clearPlayer,
    tracks,
    tracksLoading,
    skipToTrack,
    albumSaved,
    albumSavePending,
    toggleAlbumSave,
    canRemoveFromLibrary,
    appleMusicUserToken,
    nowPlayingSongId,
  } = usePlayer()

  const isAppleMusic = activeService === 'apple_music'
  const accentColor = isAppleMusic ? '#fc3c44' : '#1DB954'

  const [seekValue, setSeekValue] = useState<number | null>(null)
  const [pickerScope, setPickerScope] = useState<'album' | 'track'>('album')
  const [pickerOpened, { open: openPicker, close: closePicker }] = useDisclosure(false)

  const isPlaying = status === 'playing'
  const displayPosition = seekValue ?? position
  const progressPercent = duration > 0 ? (displayPosition / duration) * 100 : 0

  const handleToggleSave = async () => {
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

  const openAlbumPicker = () => { setPickerScope('album'); openPicker() }
  const openTrackPicker = () => { setPickerScope('track'); openPicker() }

  // Build playlist picker callbacks based on the active service
  const spotifyUris = pickerScope === 'album'
    ? tracks.map((t) => t.id)
    : nowPlayingSongId ? [nowPlayingSongId] : []

  const appleMusicSongIds = pickerScope === 'album'
    ? tracks.map((t) => t.id)
    : nowPlayingSongId ? [nowPlayingSongId] : []

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
        return getPlaylistsContainingUris(token, spotifyPls, spotifyUris)
      }

  const onAdd = async (playlistId: string) => {
    if (isAppleMusic) {
      if (!appleMusicUserToken) throw new Error('Apple Music not authorized')
      const devToken = await getAppleMusicDeveloperToken()
      await addSongsToAppleMusicPlaylist(playlistId, appleMusicSongIds, devToken, appleMusicUserToken)
      return
    }
    const token = await getSpotifyToken()
    await addTracksToPlaylist(token, playlistId, spotifyUris)
  }

  const onRemove = isAppleMusic
    ? undefined
    : async (playlistId: string) => {
        const token = await getSpotifyToken()
        await removeTracksFromPlaylist(token, playlistId, spotifyUris)
      }

  const hasCurrentTrack = isAppleMusic ? !!currentTrackName : !!currentTrackUri
  const borderTop = { borderTop: '1px solid var(--mantine-color-dark-4)' }
  const separator = '1px solid var(--mantine-color-dark-4)'

  return (
    <>
      <Stack h="100%" gap={0} style={borderTop}>

        {/* Tracklist — same UI for both services */}
        {!minimized && (
          <ScrollArea style={{ flex: 1, minHeight: 0 }} scrollbarSize={4}>
            {tracksLoading && (
              <Text size="xs" c="dimmed" px="md" py="xs">Loading tracks…</Text>
            )}
            {tracks.map((track, index) => {
              const isActive = isAppleMusic
                ? currentTrackNumber === track.trackNumber
                : track.id === currentTrackUri
              return (
                <Group
                  key={track.id}
                  px="md"
                  py={6}
                  gap="xs"
                  wrap="nowrap"
                  style={{
                    cursor: 'pointer',
                    backgroundColor: isActive ? 'var(--mantine-color-dark-6)' : 'transparent',
                  }}
                  onClick={() => skipToTrack(index)}
                >
                  <Text size="xs" w={24} ta="right" style={{ flexShrink: 0 }} c={isActive ? accentColor : 'dimmed'}>
                    {track.trackNumber}
                  </Text>
                  <Stack gap={0} style={{ flex: 1, minWidth: 0 }}>
                    <Text size="xs" fw={isActive ? 600 : 400} c={isActive ? (isAppleMusic ? 'red.4' : 'green') : 'white'} lineClamp={1}>
                      {track.name}
                    </Text>
                    <Text size="xs" c="dimmed" lineClamp={1}>{track.artist}</Text>
                  </Stack>
                  <Text size="xs" c="dimmed" style={{ flexShrink: 0 }}>{formatDuration(track.durationMs)}</Text>
                </Group>
              )
            })}
          </ScrollArea>
        )}

        {/* Bar — always visible */}
        <Group
          h={48}
          px="md"
          gap="sm"
          wrap="nowrap"
          style={{ flexShrink: 0, ...(!minimized && { borderTop: separator }) }}
        >
          <Tooltip label="Close player" withArrow>
            <ActionIcon variant="subtle" size="sm" color="gray" onClick={clearPlayer} aria-label="Close player">
              <IconX size={12} />
            </ActionIcon>
          </Tooltip>
          <Image
            src={playingAlbumMeta?.coverUrl ?? undefined}
            w={28}
            h={28}
            radius="xs"
            style={{ flexShrink: 0 }}
            fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='28' height='28'%3E%3Crect width='28' height='28' fill='%23373A40'/%3E%3C/svg%3E"
          />

          <Stack gap={1} style={{ flex: 1, minWidth: 0 }}>
            <Group gap={4} wrap="nowrap" align="center">
              <Text size="xs" style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {currentTrackName && <Text span fw={500} size="xs">{currentTrackName}</Text>}
                {currentTrackName && playingAlbumMeta?.artist && <Text span c="dimmed" size="xs"> · </Text>}
                {playingAlbumMeta?.artist && <Text span c="dimmed" size="xs">{playingAlbumMeta.artist}</Text>}
                {playingAlbumMeta?.artist && <Text span c="dimmed" size="xs"> · </Text>}
                {playingAlbumMeta?.appAlbumId ? (
                  <Anchor component={Link} to={`/albums/${playingAlbumMeta.appAlbumId}`} c="dimmed" size="xs" underline="hover">
                    {playingAlbumMeta.title ?? '—'}
                  </Anchor>
                ) : (
                  <Text span c="dimmed" size="xs">{playingAlbumMeta?.title ?? '—'}</Text>
                )}
              </Text>
              <Tooltip label={isAppleMusic ? 'Playing via Apple Music' : 'Playing via Spotify'} withArrow>
                {isAppleMusic
                  ? <IconBrandApple size={12} color="#fc3c44" style={{ flexShrink: 0 }} />
                  : <IconBrandSpotify size={12} color="#1DB954" style={{ flexShrink: 0 }} />
                }
              </Tooltip>
            </Group>
            <Group gap={4} wrap="nowrap">
              <Text size="xs" c="dimmed" ta="right" style={{ flexShrink: 0, width: 28 }}>
                {formatDuration(displayPosition)}
              </Text>
              <Slider
                style={{ flex: 1 }}
                size="xs"
                value={progressPercent}
                min={0}
                max={100}
                step={0.01}
                label={null}
                thumbSize={8}
                onChange={(val) => setSeekValue((val / 100) * duration)}
                onChangeEnd={(val) => {
                  seekTo((val / 100) * duration)
                  setSeekValue(null)
                }}
                styles={(theme) => ({
                  track: { background: theme.colors.dark[4] },
                  bar: { background: accentColor },
                  thumb: { borderColor: accentColor, background: accentColor },
                })}
              />
              <Text size="xs" c="dimmed" style={{ flexShrink: 0, width: 28 }}>
                {formatDuration(duration)}
              </Text>
            </Group>
          </Stack>

          <Group gap={4} wrap="nowrap" style={{ flexShrink: 0 }}>
            <ActionIcon variant="subtle" size="sm" color="gray" onClick={skipPrevious}>
              <IconPlayerSkipBackFilled size={12} />
            </ActionIcon>
            <ActionIcon variant="filled" color={isAppleMusic ? 'red' : 'green'} radius="xl" size="sm" onClick={togglePlay}>
              {isPlaying ? <IconPlayerPauseFilled size={12} /> : <IconPlayerPlayFilled size={12} />}
            </ActionIcon>
            <ActionIcon variant="subtle" size="sm" color="gray" onClick={skipNext}>
              <IconPlayerSkipForwardFilled size={12} />
            </ActionIcon>
            <KebabMenu
              albumSaved={albumSaved}
              savingAlbum={albumSavePending}
              canRemove={canRemoveFromLibrary}
              isAppleMusic={isAppleMusic}
              hasCurrentTrack={hasCurrentTrack}
              groupId={playingAlbumMeta?.groupId}
              groupAlbumId={playingAlbumMeta?.groupAlbumId}
              onToggleSave={handleToggleSave}
              onAddAlbum={openAlbumPicker}
              onAddTrack={openTrackPicker}
            />
            <Tooltip label={minimized ? 'Show tracklist' : 'Hide tracklist'} withArrow>
              <ActionIcon variant="subtle" size="sm" color="gray" onClick={toggleMinimized} aria-label={minimized ? 'Show tracklist' : 'Hide tracklist'}>
                {minimized ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>

      </Stack>

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

// ── Kebab menu ────────────────────────────────────────────────────────────────

interface KebabMenuProps {
  albumSaved: boolean
  savingAlbum: boolean
  canRemove: boolean
  isAppleMusic: boolean
  hasCurrentTrack: boolean
  groupId?: number
  groupAlbumId?: number
  onToggleSave: () => void
  onAddAlbum: () => void
  onAddTrack: () => void
}

function KebabMenu({
  albumSaved,
  savingAlbum,
  canRemove,
  isAppleMusic,
  hasCurrentTrack,
  groupId,
  groupAlbumId,
  onToggleSave,
  onAddAlbum,
  onAddTrack,
}: KebabMenuProps) {
  const saveLabel = isAppleMusic
    ? 'Save to Library'
    : albumSaved && canRemove ? 'Remove from library' : 'Save album'
  const SaveIcon = albumSaved && canRemove
    ? <IconHeartFilled size={14} color="var(--mantine-color-green-5)" />
    : <IconHeart size={14} />

  return (
    <Menu shadow="md" width={210} position="top-end" withinPortal>
      <Menu.Target>
        <Tooltip label="More options" withArrow>
          <ActionIcon variant="subtle" size="sm" color="gray" aria-label="More options">
            <IconDots size={14} />
          </ActionIcon>
        </Tooltip>
      </Menu.Target>
      <Menu.Dropdown>
        {groupId && (
          <>
            <Menu.Item
              component={Link}
              to={groupAlbumId
                ? `/groups/${groupId}?tab=spin&album=${groupAlbumId}`
                : `/groups/${groupId}?tab=spin`}
              leftSection={<IconMessageCircle size={14} />}
            >
              Go to review
            </Menu.Item>
            <Divider />
          </>
        )}
        <Menu.Item leftSection={SaveIcon} onClick={onToggleSave} disabled={savingAlbum}>
          {saveLabel}
        </Menu.Item>
        <Menu.Item leftSection={<IconPlaylistAdd size={14} />} onClick={onAddAlbum}>
          Add album to playlist
        </Menu.Item>
        <Divider />
        <Menu.Item leftSection={<IconPlaylistAdd size={14} />} onClick={onAddTrack} disabled={!hasCurrentTrack}>
          Add track to playlist
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  )
}
