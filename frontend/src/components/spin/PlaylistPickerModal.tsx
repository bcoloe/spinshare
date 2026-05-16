import { useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Group,
  Image,
  Loader,
  Modal,
  Stack,
  Text,
  TextInput,
} from '@mantine/core'
import { IconAlertCircle, IconCheck, IconMusic, IconSearch } from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'

export interface PickablePlaylist {
  id: string
  name: string
  imageUrl: string | null
}

interface Props {
  opened: boolean
  onClose: () => void
  title?: string
  fetchPlaylists: () => Promise<PickablePlaylist[]>
  checkContaining?: (playlists: PickablePlaylist[]) => Promise<Set<string>>
  onAdd: (playlistId: string) => Promise<void>
  onRemove?: (playlistId: string) => Promise<void>
}

export default function PlaylistPickerModal({
  opened,
  onClose,
  title = 'Add to playlist',
  fetchPlaylists,
  checkContaining,
  onAdd,
  onRemove,
}: Props) {
  const [playlists, setPlaylists] = useState<PickablePlaylist[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [addedIds, setAddedIds] = useState<Set<string>>(new Set())
  const [loadingIds, setLoadingIds] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (!opened) return
    let cancelled = false
    setLoading(true)
    setError(null)
    setQuery('')
    setAddedIds(new Set())
    ;(async () => {
      try {
        const data = await fetchPlaylists()
        if (cancelled) return
        setPlaylists(data)
        if (checkContaining) {
          const existing = await checkContaining(data)
          if (!cancelled) setAddedIds(existing)
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load playlists.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [opened])

  const filtered = query.trim()
    ? playlists.filter((p) => p.name.toLowerCase().includes(query.toLowerCase()))
    : playlists

  const handleToggle = async (playlist: PickablePlaylist) => {
    if (loadingIds.has(playlist.id)) return
    const isAdded = addedIds.has(playlist.id)
    if (isAdded && !onRemove) return

    setLoadingIds((prev) => new Set(prev).add(playlist.id))
    try {
      if (isAdded && onRemove) {
        await onRemove(playlist.id)
        setAddedIds((prev) => { const next = new Set(prev); next.delete(playlist.id); return next })
        notifications.show({ message: `Removed from ${playlist.name}` })
      } else {
        await onAdd(playlist.id)
        setAddedIds((prev) => new Set(prev).add(playlist.id))
        notifications.show({ color: 'green', message: `Added to ${playlist.name}` })
      }
    } catch (err) {
      notifications.show({ color: 'red', message: err instanceof Error ? err.message : 'Could not update playlist' })
    } finally {
      setLoadingIds((prev) => { const next = new Set(prev); next.delete(playlist.id); return next })
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title={title} size="sm">
      {loading ? (
        <Group justify="center" py="xl">
          <Loader size="sm" />
        </Group>
      ) : error ? (
        <Alert icon={<IconAlertCircle size={16} />} color="orange">{error}</Alert>
      ) : playlists.length === 0 ? (
        <Text size="sm" c="dimmed" ta="center" py="xl">No playlists found.</Text>
      ) : (
        <Stack gap="sm">
          <TextInput
            placeholder="Search playlists…"
            leftSection={<IconSearch size={14} />}
            value={query}
            onChange={(e) => setQuery(e.currentTarget.value)}
            size="xs"
          />
          {filtered.length === 0 ? (
            <Text size="sm" c="dimmed" ta="center" py="md">No matching playlists.</Text>
          ) : (
            <Stack gap={2}>
              {filtered.map((pl) => {
                const isAdded = addedIds.has(pl.id)
                const isLoading = loadingIds.has(pl.id)
                const clickable = !isAdded || !!onRemove
                return (
                  <Group
                    key={pl.id}
                    gap="sm"
                    wrap="nowrap"
                    px={10}
                    py={8}
                    style={(theme) => ({
                      borderRadius: theme.radius.sm,
                      cursor: isLoading || !clickable ? 'default' : 'pointer',
                      background: isAdded ? theme.colors.green[9] : 'transparent',
                      transition: 'background 150ms ease',
                    })}
                    onClick={() => clickable && handleToggle(pl)}
                  >
                    {isLoading ? (
                      <Loader size={14} color={isAdded ? 'green' : 'gray'} style={{ flexShrink: 0 }} />
                    ) : pl.imageUrl ? (
                      <Image src={pl.imageUrl} w={32} h={32} radius="xs" style={{ flexShrink: 0 }} />
                    ) : (
                      <Box
                        w={32}
                        h={32}
                        style={(theme) => ({
                          background: isAdded ? theme.colors.green[8] : theme.colors.dark[4],
                          borderRadius: theme.radius.xs,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                        })}
                      >
                        <IconMusic size={14} />
                      </Box>
                    )}
                    <Text size="sm" lineClamp={1} style={{ flex: 1 }} c={isAdded ? 'green.3' : undefined}>
                      {pl.name}
                    </Text>
                    {isAdded && !isLoading && (
                      <IconCheck size={14} color="var(--mantine-color-green-4)" style={{ flexShrink: 0 }} />
                    )}
                  </Group>
                )
              })}
            </Stack>
          )}
        </Stack>
      )}
    </Modal>
  )
}
