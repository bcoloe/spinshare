import { useEffect } from 'react'
import {
  ActionIcon,
  Alert,
  Anchor,
  Box,
  Group,
  Image,
  Skeleton,
  Stack,
  Text,
} from '@mantine/core'
import {
  IconAlertCircle,
  IconBrandSpotify,
  IconExternalLink,
  IconPlayerPauseFilled,
  IconPlayerPlayFilled,
  IconPlayerSkipBackFilled,
  IconPlayerSkipForwardFilled,
} from '@tabler/icons-react'
import { useSpotifyPlayer } from '../../hooks/useSpotifyPlayer'

interface Props {
  spotifyAlbumId: string
  hasSpotify: boolean
}

export default function SpotifyPlayer({ spotifyAlbumId, hasSpotify }: Props) {
  const { status, currentTrack, deviceId, togglePlay, nextTrack, prevTrack, startAlbum } =
    useSpotifyPlayer(hasSpotify)

  // Auto-start the album once the device is ready
  useEffect(() => {
    if (status === 'ready' && deviceId) {
      startAlbum(spotifyAlbumId)
    }
  }, [status, deviceId, spotifyAlbumId])

  const openLink = `https://open.spotify.com/album/${spotifyAlbumId}`

  if (!hasSpotify) {
    return <IframeFallback spotifyAlbumId={spotifyAlbumId} />
  }

  if (status === 'loading' || status === 'idle') {
    return <Skeleton h={80} radius="md" />
  }

  if (status === 'premium_required') {
    return (
      <Stack gap="xs">
        <Alert
          icon={<IconBrandSpotify size={16} />}
          color="green"
          title="Spotify Premium required"
        >
          Full playback is only available with Spotify Premium.
        </Alert>
        <IframeFallback spotifyAlbumId={spotifyAlbumId} />
      </Stack>
    )
  }

  if (status === 'reconnect_required') {
    return (
      <Alert icon={<IconAlertCircle size={16} />} color="orange" title="Spotify disconnected">
        Your Spotify session has expired.{' '}
        <Anchor href="/profile" size="sm">Reconnect in your profile</Anchor> to re-enable playback.
      </Alert>
    )
  }

  if (status === 'not_connected') {
    return <IframeFallback spotifyAlbumId={spotifyAlbumId} />
  }

  if (status === 'error') {
    return (
      <Stack gap="xs">
        <Alert icon={<IconAlertCircle size={16} />} color="red" title="Playback unavailable">
          Could not initialize the Spotify player.
        </Alert>
        <IframeFallback spotifyAlbumId={spotifyAlbumId} />
      </Stack>
    )
  }

  const isActive = status === 'playing' || status === 'paused'

  return (
    <Stack gap="xs">
      <Box
        p="sm"
        style={(theme) => ({
          background: theme.colors.dark[7],
          borderRadius: theme.radius.md,
          border: `1px solid ${theme.colors.dark[4]}`,
        })}
      >
        <Group gap="sm" wrap="nowrap">
          {currentTrack?.coverUrl ? (
            <Image src={currentTrack.coverUrl} w={52} h={52} radius="sm" />
          ) : (
            <Box
              w={52}
              h={52}
              style={(theme) => ({
                background: theme.colors.dark[5],
                borderRadius: theme.radius.sm,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              })}
            >
              <IconBrandSpotify size={24} color="#1DB954" />
            </Box>
          )}

          <Stack gap={2} style={{ flex: 1, minWidth: 0 }}>
            <Text size="sm" fw={500} lineClamp={1}>
              {isActive && currentTrack ? currentTrack.name : 'Starting playback…'}
            </Text>
            <Text size="xs" c="dimmed" lineClamp={1}>
              {isActive && currentTrack ? currentTrack.artists : 'Spotify'}
            </Text>
          </Stack>

          <Group gap="xs" wrap="nowrap">
            <ActionIcon variant="subtle" size="sm" onClick={prevTrack} disabled={!isActive}>
              <IconPlayerSkipBackFilled size={14} />
            </ActionIcon>
            <ActionIcon variant="filled" color="green" radius="xl" size="md" onClick={togglePlay}>
              {status === 'playing'
                ? <IconPlayerPauseFilled size={14} />
                : <IconPlayerPlayFilled size={14} />}
            </ActionIcon>
            <ActionIcon variant="subtle" size="sm" onClick={nextTrack} disabled={!isActive}>
              <IconPlayerSkipForwardFilled size={14} />
            </ActionIcon>
          </Group>
        </Group>
      </Box>

      <Anchor href={openLink} target="_blank" rel="noopener noreferrer" size="sm" c="dimmed">
        <Group gap={4}>
          <IconExternalLink size={14} />
          Open in Spotify
        </Group>
      </Anchor>
    </Stack>
  )
}

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
