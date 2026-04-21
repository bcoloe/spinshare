import { useEffect, useState } from 'react'
import {
  Box,
  Group,
  Image,
  Loader,
  Modal,
  Stack,
  Text,
  UnstyledButton,
} from '@mantine/core'
import { IconMusic } from '@tabler/icons-react'
import { fetchUserPlaylists, type SpotifyPlaylist } from '../../services/spotifyApiClient'
import { getSpotifyToken } from '../../services/streamingService'

interface Props {
  opened: boolean
  onClose: () => void
  onSelect: (playlist: SpotifyPlaylist) => void
  title?: string
}

export default function PlaylistPickerModal({ opened, onClose, onSelect, title = 'Add to playlist' }: Props) {
  const [playlists, setPlaylists] = useState<SpotifyPlaylist[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!opened) return
    let cancelled = false
    setLoading(true)
    getSpotifyToken()
      .then((token) => fetchUserPlaylists(token))
      .then((data) => { if (!cancelled) setPlaylists(data) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [opened])

  return (
    <Modal opened={opened} onClose={onClose} title={title} size="sm">
      {loading ? (
        <Group justify="center" py="xl">
          <Loader size="sm" />
        </Group>
      ) : playlists.length === 0 ? (
        <Text size="sm" c="dimmed" ta="center" py="xl">No playlists found.</Text>
      ) : (
        <Stack gap={2}>
          {playlists.map((pl) => (
            <UnstyledButton
              key={pl.id}
              onClick={() => { onSelect(pl); onClose() }}
              style={(theme) => ({
                padding: '8px 10px',
                borderRadius: theme.radius.sm,
                '&:hover': { background: theme.colors.dark[5] },
              })}
            >
              <Group gap="sm" wrap="nowrap">
                {pl.imageUrl ? (
                  <Image src={pl.imageUrl} w={36} h={36} radius="xs" />
                ) : (
                  <Box
                    w={36}
                    h={36}
                    style={(theme) => ({
                      background: theme.colors.dark[5],
                      borderRadius: theme.radius.xs,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    })}
                  >
                    <IconMusic size={16} />
                  </Box>
                )}
                <Stack gap={0} style={{ minWidth: 0 }}>
                  <Text size="sm" lineClamp={1}>{pl.name}</Text>
                  <Text size="xs" c="dimmed">{pl.tracksTotal} tracks</Text>
                </Stack>
              </Group>
            </UnstyledButton>
          ))}
        </Stack>
      )}
    </Modal>
  )
}
