import { useState } from 'react'
import {
  ActionIcon,
  Button,
  Group,
  Image,
  Loader,
  Modal,
  SimpleGrid,
  Stack,
  Tabs,
  Text,
  TextInput,
} from '@mantine/core'
import { useDebouncedValue } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react'
import { useAlbumSearch, useNominateAlbum, useSpotifyLibrary } from '../../hooks/useAlbums'
import { useAuth } from '../../hooks/useAuth'
import { ApiError } from '../../services/apiClient'
import type { AlbumSearchResult } from '../../services/albumSearchService'

const PAGE_SIZE = 20

interface Props {
  groupId: number
  opened: boolean
  onClose: () => void
}

function AlbumRow({
  result,
  nominated,
  isPending,
  onNominate,
}: {
  result: AlbumSearchResult
  nominated: boolean
  isPending: boolean
  onNominate: (result: AlbumSearchResult) => void
}) {
  return (
    <Group justify="space-between" wrap="nowrap">
      <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
        <Image
          src={result.cover_url ?? undefined}
          w={44}
          h={44}
          radius="sm"
          fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='44' height='44'%3E%3Crect width='44' height='44' fill='%23373A40'/%3E%3C/svg%3E"
        />
        <div style={{ minWidth: 0 }}>
          <Text size="sm" fw={500} lineClamp={1}>{result.title}</Text>
          <Text size="xs" c="dimmed" lineClamp={1}>{result.artist}</Text>
        </div>
      </Group>
      <Button
        size="xs"
        variant={nominated ? 'filled' : 'light'}
        color={nominated ? 'green' : 'violet'}
        disabled={nominated}
        loading={isPending}
        onClick={() => onNominate(result)}
        style={{ flexShrink: 0 }}
      >
        {nominated ? 'Nominated' : 'Nominate'}
      </Button>
    </Group>
  )
}

export default function AlbumSearchModal({ groupId, opened, onClose }: Props) {
  const { user } = useAuth()
  const [query, setQuery] = useState('')
  const [artistFilter, setArtistFilter] = useState('')
  const [albumFilter, setAlbumFilter] = useState('')
  const [nominated, setNominated] = useState<Set<string>>(new Set())
  const [libraryOffset, setLibraryOffset] = useState(0)

  const [debouncedQuery] = useDebouncedValue(query, 300)
  const [debouncedArtist] = useDebouncedValue(artistFilter, 300)
  const [debouncedAlbum] = useDebouncedValue(albumFilter, 300)

  const searchParams = {
    q: debouncedQuery || undefined,
    artist: debouncedArtist || undefined,
    album: debouncedAlbum || undefined,
  }
  const isSearching =
    (debouncedQuery?.length ?? 0) >= 2 ||
    (debouncedArtist?.length ?? 0) >= 2 ||
    (debouncedAlbum?.length ?? 0) >= 2

  const { data: searchResults, isLoading: searchLoading } = useAlbumSearch(searchParams)
  const { data: libraryPage, isLoading: libraryLoading } = useSpotifyLibrary(libraryOffset)
  const nominate = useNominateAlbum(groupId)

  const handleNominate = async (result: AlbumSearchResult) => {
    try {
      await nominate.mutateAsync(result)
      setNominated((prev) => new Set(prev).add(result.spotify_album_id))
      notifications.show({ color: 'green', message: `"${result.title}" nominated` })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not nominate album'
      notifications.show({ color: 'red', message })
    }
  }

  const handleClose = () => {
    setQuery('')
    setArtistFilter('')
    setAlbumFilter('')
    setNominated(new Set())
    setLibraryOffset(0)
    onClose()
  }

  const totalPages = libraryPage ? Math.ceil(libraryPage.total / PAGE_SIZE) : 0
  const currentPage = Math.floor(libraryOffset / PAGE_SIZE) + 1

  return (
    <Modal opened={opened} onClose={handleClose} title="Nominate an album" size="md" centered>
      <Tabs defaultValue="search">
        <Tabs.List mb="md">
          <Tabs.Tab value="search">Search</Tabs.Tab>
          {user?.has_spotify && <Tabs.Tab value="library">My Library</Tabs.Tab>}
        </Tabs.List>

        <Tabs.Panel value="search">
          <Stack gap="md">
            <TextInput
              placeholder="Search albums…"
              value={query}
              onChange={(e) => setQuery(e.currentTarget.value)}
              autoFocus
              rightSection={searchLoading && isSearching ? <Loader size="xs" /> : null}
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
            {searchResults?.map((r) => (
              <AlbumRow
                key={r.spotify_album_id}
                result={r}
                nominated={nominated.has(r.spotify_album_id)}
                isPending={nominate.isPending}
                onNominate={handleNominate}
              />
            ))}
            {searchResults?.length === 0 && isSearching && !searchLoading && (
              <Text size="sm" c="dimmed">No albums found</Text>
            )}
          </Stack>
        </Tabs.Panel>

        {user?.has_spotify && (
          <Tabs.Panel value="library">
            <Stack gap="md">
              {libraryLoading && <Loader size="sm" mx="auto" />}
              {libraryPage?.items.map((r) => (
                <AlbumRow
                  key={r.spotify_album_id}
                  result={r}
                  nominated={nominated.has(r.spotify_album_id)}
                  isPending={nominate.isPending}
                  onNominate={handleNominate}
                />
              ))}
              {libraryPage && libraryPage.total > PAGE_SIZE && (
                <Group justify="space-between" align="center">
                  <ActionIcon
                    variant="subtle"
                    disabled={libraryOffset === 0}
                    onClick={() => setLibraryOffset((o) => Math.max(0, o - PAGE_SIZE))}
                  >
                    <IconChevronLeft size={16} />
                  </ActionIcon>
                  <Text size="xs" c="dimmed">
                    Page {currentPage} of {totalPages}
                  </Text>
                  <ActionIcon
                    variant="subtle"
                    disabled={libraryOffset + PAGE_SIZE >= libraryPage.total}
                    onClick={() => setLibraryOffset((o) => o + PAGE_SIZE)}
                  >
                    <IconChevronRight size={16} />
                  </ActionIcon>
                </Group>
              )}
            </Stack>
          </Tabs.Panel>
        )}
      </Tabs>
    </Modal>
  )
}
