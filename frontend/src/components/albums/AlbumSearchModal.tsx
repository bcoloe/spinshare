import { useState } from 'react'
import {
  Button,
  Group,
  Image,
  Loader,
  Modal,
  Stack,
  Text,
  TextInput,
} from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useAlbumSearch, useNominateAlbum } from '../../hooks/useAlbums'
import { ApiError } from '../../services/apiClient'

interface Props {
  groupId: number
  opened: boolean
  onClose: () => void
}

export default function AlbumSearchModal({ groupId, opened, onClose }: Props) {
  const [query, setQuery] = useState('')
  const [nominated, setNominated] = useState<Set<string>>(new Set())
  const [debouncedQuery] = useDebouncedValue(query, 300)
  const { data: results, isLoading } = useAlbumSearch(debouncedQuery)
  const nominate = useNominateAlbum(groupId)

  const handleNominate = async (spotifyId: string, title: string, result: NonNullable<typeof results>[number]) => {
    if (!result) return
    try {
      await nominate.mutateAsync(result)
      setNominated((prev) => new Set(prev).add(spotifyId))
      notifications.show({ color: 'green', message: `"${title}" nominated` })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not nominate album'
      notifications.show({ color: 'red', message })
    }
  }

  const handleClose = () => {
    setQuery('')
    setNominated(new Set())
    onClose()
  }

  return (
    <Modal opened={opened} onClose={handleClose} title="Nominate an album" size="md" centered>
      <Stack gap="md">
        <TextInput
          placeholder="Search albums…"
          value={query}
          onChange={(e) => setQuery(e.currentTarget.value)}
          autoFocus
          rightSection={isLoading && debouncedQuery ? <Loader size="xs" /> : null}
        />
        {results?.map((r) => (
          <Group key={r.spotify_album_id} justify="space-between" wrap="nowrap">
            <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
              <Image
                src={r.cover_url ?? undefined}
                w={44}
                h={44}
                radius="sm"
                fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='44' height='44'%3E%3Crect width='44' height='44' fill='%23373A40'/%3E%3C/svg%3E"
              />
              <div style={{ minWidth: 0 }}>
                <Text size="sm" fw={500} lineClamp={1}>{r.title}</Text>
                <Text size="xs" c="dimmed" lineClamp={1}>{r.artist}</Text>
              </div>
            </Group>
            <Button
              size="xs"
              variant={nominated.has(r.spotify_album_id) ? 'filled' : 'light'}
              color={nominated.has(r.spotify_album_id) ? 'green' : 'violet'}
              disabled={nominated.has(r.spotify_album_id)}
              loading={nominate.isPending}
              onClick={() => handleNominate(r.spotify_album_id, r.title, r)}
              style={{ flexShrink: 0 }}
            >
              {nominated.has(r.spotify_album_id) ? 'Nominated' : 'Nominate'}
            </Button>
          </Group>
        ))}
        {results?.length === 0 && debouncedQuery.length >= 2 && !isLoading && (
          <Text size="sm" c="dimmed">No albums found</Text>
        )}
      </Stack>
    </Modal>
  )
}
