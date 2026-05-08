import { useState } from 'react'
import {
  Button,
  Group,
  Image,
  Loader,
  Modal,
  Select,
  SimpleGrid,
  Skeleton,
  Stack,
  Tabs,
  Text,
  TextInput,
} from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useAlbumSearch, useMyNominations, useNominateAlbum, useNominateFromPool } from '../../hooks/useAlbums'
import { useMyGroups } from '../../hooks/useGroups'
import { useAuth } from '../../hooks/useAuth'
import { ApiError } from '../../services/apiClient'

interface Props {
  groupId?: number  // when omitted, a group picker is shown at the top
  opened: boolean
  onClose: () => void
}

export default function AlbumSearchModal({ groupId, opened, onClose }: Props) {
  const { user } = useAuth()
  const { data: groups = [] } = useMyGroups(user?.username ?? '')

  const [pickedGroupId, setPickedGroupId] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [artistFilter, setArtistFilter] = useState('')
  const [albumFilter, setAlbumFilter] = useState('')
  const [poolFilter, setPoolFilter] = useState('')
  const [nominated, setNominated] = useState<Set<string>>(new Set())
  const [nominatedFromPool, setNominatedFromPool] = useState<Set<number>>(new Set())

  const [debouncedQuery] = useDebouncedValue(query, 300)
  const [debouncedArtist] = useDebouncedValue(artistFilter, 300)
  const [debouncedAlbum] = useDebouncedValue(albumFilter, 300)

  const ROLE_RANK: Record<string, number> = { owner: 0, admin: 1, member: 2 }
  const nominatableGroups = groups.filter((g) => {
    if (!g.current_user_role) return false
    const minRole = g.settings?.min_role_to_nominate ?? 'member'
    return (ROLE_RANK[g.current_user_role] ?? 99) <= (ROLE_RANK[minRole] ?? 99)
  })

  const effectiveGroupId = groupId ?? (pickedGroupId ? Number(pickedGroupId) : undefined)

  const searchParams = {
    q: debouncedQuery || undefined,
    artist: debouncedArtist || undefined,
    album: debouncedAlbum || undefined,
  }
  const isSearching =
    (debouncedQuery?.length ?? 0) >= 2 ||
    (debouncedArtist?.length ?? 0) >= 2 ||
    (debouncedAlbum?.length ?? 0) >= 2
  const { data: results, isLoading } = useAlbumSearch(searchParams)
  const { data: poolItems = [], isLoading: poolLoading } = useMyNominations()
  const nominate = useNominateAlbum(effectiveGroupId ?? 0)
  const nominateFromPool = useNominateFromPool(effectiveGroupId ?? 0)

  const poolFiltered = poolItems.filter((item) => {
    if (effectiveGroupId !== undefined && item.nominated_group_ids.includes(effectiveGroupId)) return false
    if (!poolFilter) return true
    const q = poolFilter.toLowerCase()
    return item.album.title.toLowerCase().includes(q) || item.album.artist.toLowerCase().includes(q)
  })

  const handleNominate = async (spotifyId: string, title: string, result: NonNullable<typeof results>[number]) => {
    if (!result || !effectiveGroupId) return
    try {
      await nominate.mutateAsync(result)
      setNominated((prev) => new Set(prev).add(spotifyId))
      notifications.show({ color: 'green', message: `"${title}" nominated` })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not nominate album'
      notifications.show({ color: 'red', message })
    }
  }

  const handleNominateFromPool = async (albumId: number, title: string) => {
    if (!effectiveGroupId) return
    try {
      await nominateFromPool.mutateAsync(albumId)
      setNominatedFromPool((prev) => new Set(prev).add(albumId))
      notifications.show({ color: 'green', message: `"${title}" nominated` })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not nominate album'
      notifications.show({ color: 'red', message })
    }
  }

  const handleClose = () => {
    setPickedGroupId(null)
    setQuery('')
    setArtistFilter('')
    setAlbumFilter('')
    setPoolFilter('')
    setNominated(new Set())
    setNominatedFromPool(new Set())
    onClose()
  }

  return (
    <Modal opened={opened} onClose={handleClose} title="Nominate an album" size="md" centered>
      <Stack gap="md">
        {groupId === undefined && (
          <Select
            label="Group"
            placeholder="Choose a group…"
            data={nominatableGroups.map((g) => ({ value: String(g.id), label: g.name }))}
            value={pickedGroupId}
            onChange={setPickedGroupId}
          />
        )}

        <Tabs defaultValue="spotify">
          <Tabs.List mb="md">
            <Tabs.Tab value="spotify">Spotify search</Tabs.Tab>
            <Tabs.Tab value="pool">My nominations</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="spotify">
            <Stack gap="md">
              <TextInput
                placeholder="Search albums…"
                value={query}
                onChange={(e) => setQuery(e.currentTarget.value)}
                autoFocus
                rightSection={isLoading && isSearching ? <Loader size="xs" /> : null}
              />
              <SimpleGrid cols={2} spacing="sm">
                <TextInput
                  placeholder="Filter by artist…"
                  value={artistFilter}
                  onChange={(e) => setArtistFilter(e.currentTarget.value)}
                  size="sm"
                />
                <TextInput
                  placeholder="Filter by album…"
                  value={albumFilter}
                  onChange={(e) => setAlbumFilter(e.currentTarget.value)}
                  size="sm"
                />
              </SimpleGrid>
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
                    disabled={nominated.has(r.spotify_album_id) || !effectiveGroupId}
                    loading={nominate.isPending}
                    onClick={() => handleNominate(r.spotify_album_id, r.title, r)}
                    style={{ flexShrink: 0 }}
                  >
                    {nominated.has(r.spotify_album_id) ? 'Nominated' : 'Nominate'}
                  </Button>
                </Group>
              ))}
              {results?.length === 0 && isSearching && !isLoading && (
                <Text size="sm" c="dimmed">No albums found</Text>
              )}
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="pool">
            <Stack gap="md">
              <TextInput
                placeholder="Filter by album or artist…"
                value={poolFilter}
                onChange={(e) => setPoolFilter(e.currentTarget.value)}
              />
              {poolLoading ? (
                <Stack gap="xs">
                  {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} h={52} radius="sm" />)}
                </Stack>
              ) : poolFiltered.length === 0 ? (
                <Text size="sm" c="dimmed">
                  {poolItems.length === 0
                    ? 'You have no prior nominations to draw from.'
                    : effectiveGroupId
                    ? 'All your previously nominated albums are already in this group.'
                    : 'No nominations match your filter.'}
                </Text>
              ) : (
                poolFiltered.map((item) => {
                  const alreadyDone = nominatedFromPool.has(item.album.id)
                  return (
                    <Group key={item.album.id} justify="space-between" wrap="nowrap">
                      <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
                        <Image
                          src={item.album.cover_url ?? undefined}
                          w={44}
                          h={44}
                          radius="sm"
                          fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='44' height='44'%3E%3Crect width='44' height='44' fill='%23373A40'/%3E%3C/svg%3E"
                        />
                        <div style={{ minWidth: 0 }}>
                          <Text size="sm" fw={500} lineClamp={1}>{item.album.title}</Text>
                          <Text size="xs" c="dimmed" lineClamp={1}>{item.album.artist}</Text>
                        </div>
                      </Group>
                      <Button
                        size="xs"
                        variant={alreadyDone ? 'filled' : 'light'}
                        color={alreadyDone ? 'green' : 'violet'}
                        disabled={alreadyDone || !effectiveGroupId}
                        loading={nominateFromPool.isPending}
                        onClick={() => handleNominateFromPool(item.album.id, item.album.title)}
                        style={{ flexShrink: 0 }}
                      >
                        {alreadyDone ? 'Nominated' : 'Nominate'}
                      </Button>
                    </Group>
                  )
                })
              )}
            </Stack>
          </Tabs.Panel>
        </Tabs>
      </Stack>
    </Modal>
  )
}
