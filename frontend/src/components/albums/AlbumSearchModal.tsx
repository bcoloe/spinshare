import { useState, useEffect, useRef } from 'react'
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
import { useMutation } from '@tanstack/react-query'
import { notifications } from '@mantine/notifications'
import { useAlbumSearch, useMyNominations, useNominateAlbum, useNominateFromPool } from '../../hooks/useAlbums'
import { useMyGroups } from '../../hooks/useGroups'
import { useAuth } from '../../hooks/useAuth'
import { ApiError } from '../../services/apiClient'
import { albumSearchService } from '../../services/albumSearchService'
import type { AlbumResponse } from '../../types/album'

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
  const [nominated, setNominated] = useState<Set<string | null>>(new Set())
  const [nominatedFromPool, setNominatedFromPool] = useState<Set<number>>(new Set())

  // URL tab state
  const [urlInput, setUrlInput] = useState('')
  const [manualArtist, setManualArtist] = useState('')
  const [manualAlbum, setManualAlbum] = useState('')
  const [showManualFields, setShowManualFields] = useState(false)
  const [resolvedAlbum, setResolvedAlbum] = useState<AlbumResponse | null>(null)
  const [nominatedByUrl, setNominatedByUrl] = useState<Set<number>>(new Set())

  const [debouncedQuery] = useDebouncedValue(query, 300)
  const [debouncedArtist] = useDebouncedValue(artistFilter, 300)
  const [debouncedAlbum] = useDebouncedValue(albumFilter, 300)
  const [debouncedUrl] = useDebouncedValue(urlInput, 600)

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
  const {
    data: searchData,
    isLoading,
    isFetching,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    error: searchError,
  } = useAlbumSearch(searchParams)

  const allResults = searchData?.pages.flatMap((p) => p.items) ?? []

  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const sentinelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const sentinel = sentinelRef.current
    const container = scrollContainerRef.current
    if (!sentinel || !container || !hasNextPage) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !isFetchingNextPage) fetchNextPage()
      },
      { root: container, threshold: 0 },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  useEffect(() => {
    if (!searchError) return
    const message =
      searchError instanceof ApiError && searchError.status === 429
        ? 'Spotify is rate-limited right now — please wait a moment and try again'
        : 'Album search failed — please try again'
    notifications.show({ color: 'red', message })
  }, [searchError])

  const { data: poolItems = [], isLoading: poolLoading } = useMyNominations()
  const nominate = useNominateAlbum(effectiveGroupId ?? 0)
  const nominateFromPool = useNominateFromPool(effectiveGroupId ?? 0)

  const poolFiltered = poolItems.filter((item) => {
    if (effectiveGroupId !== undefined && item.nominated_group_ids.includes(effectiveGroupId)) return false
    if (!poolFilter) return true
    const q = poolFilter.toLowerCase()
    return item.album.title.toLowerCase().includes(q) || item.album.artist.toLowerCase().includes(q)
  })

  const albumKey = (r: (typeof allResults)[number]) =>
    r.spotify_album_id ?? r.apple_music_album_id ?? r.youtube_music_id ?? String(r.album_id)

  const handleNominate = async (result: (typeof allResults)[number]) => {
    if (!result || !effectiveGroupId) return
    try {
      await nominate.mutateAsync(result)
      setNominated((prev) => new Set(prev).add(albumKey(result)))
      notifications.show({ color: 'green', message: `"${result.title}" nominated` })
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

  // ── URL tab ──────────────────────────────────────────────────────────────

  const resolveUrlMutation = useMutation({
    mutationFn: ({ url, artist, album }: { url: string; artist?: string; album?: string }) =>
      albumSearchService.resolveUrl(url, artist, album),
    onSuccess: (album) => {
      setResolvedAlbum(album)
      setShowManualFields(false)
    },
    onError: (err) => {
      if (
        err instanceof ApiError &&
        err.status === 422 &&
        err.message.toLowerCase().includes('artist')
      ) {
        setShowManualFields(true)
      }
    },
  })

  useEffect(() => {
    if (!debouncedUrl.startsWith('http')) return
    setResolvedAlbum(null)
    setShowManualFields(false)
    resolveUrlMutation.mutate({ url: debouncedUrl })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedUrl])

  const handleManualResolve = () => {
    if (!debouncedUrl || !manualArtist || !manualAlbum) return
    setResolvedAlbum(null)
    resolveUrlMutation.mutate({ url: debouncedUrl, artist: manualArtist, album: manualAlbum })
  }

  const handleNominateResolved = async () => {
    if (!resolvedAlbum || !effectiveGroupId) return
    try {
      await nominateFromPool.mutateAsync(resolvedAlbum.id)
      setNominatedByUrl((prev) => new Set(prev).add(resolvedAlbum.id))
      notifications.show({ color: 'green', message: `"${resolvedAlbum.title}" nominated` })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not nominate album'
      notifications.show({ color: 'red', message })
    }
  }

  const urlResolved = !!resolvedAlbum
  const urlNominated = resolvedAlbum ? nominatedByUrl.has(resolvedAlbum.id) : false
  const urlError =
    resolveUrlMutation.isError && !showManualFields
      ? resolveUrlMutation.error instanceof ApiError
        ? resolveUrlMutation.error.message
        : 'Could not resolve this URL'
      : null

  // ────────────────────────────────────────────────────────────────────────

  const handleClose = () => {
    setPickedGroupId(null)
    setQuery('')
    setArtistFilter('')
    setAlbumFilter('')
    setPoolFilter('')
    setNominated(new Set())
    setNominatedFromPool(new Set())
    setUrlInput('')
    setManualArtist('')
    setManualAlbum('')
    setShowManualFields(false)
    setResolvedAlbum(null)
    setNominatedByUrl(new Set())
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
            <Tabs.Tab value="spotify">Search</Tabs.Tab>
            <Tabs.Tab value="url">Paste URL</Tabs.Tab>
            <Tabs.Tab value="pool">My nominations</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="spotify">
            <Stack gap="md">
              <TextInput
                placeholder="Search albums…"
                value={query}
                onChange={(e) => setQuery(e.currentTarget.value)}
                autoFocus
                rightSection={isFetching && isSearching && !isFetchingNextPage ? <Loader size="xs" /> : null}
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
              <div ref={scrollContainerRef} style={{ maxHeight: 340, overflowY: 'auto' }}>
                <Stack gap="md">
                  {allResults.map((r) => {
                    const key = albumKey(r)
                    const isNominated = nominated.has(key)
                    return (
                      <Group key={key} justify="space-between" wrap="nowrap">
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
                          variant={isNominated ? 'filled' : 'light'}
                          color={isNominated ? 'green' : 'violet'}
                          disabled={isNominated || !effectiveGroupId}
                          loading={nominate.isPending}
                          onClick={() => handleNominate(r)}
                          style={{ flexShrink: 0 }}
                        >
                          {isNominated ? 'Nominated' : 'Nominate'}
                        </Button>
                      </Group>
                    )
                  })}
                  {hasNextPage && <div ref={sentinelRef} style={{ height: 1 }} />}
                  {isFetchingNextPage && <Loader size="xs" mx="auto" display="block" />}
                </Stack>
              </div>
              {isSearching && !isLoading && (
                searchError ? (
                  <Text size="sm" c="red.4">
                    {searchError instanceof ApiError && searchError.status === 429
                      ? 'Spotify is rate-limited right now — please wait a moment and try again'
                      : 'Album search failed — please try again'}
                  </Text>
                ) : allResults.length === 0 ? (
                  <Text size="sm" c="dimmed">No albums found</Text>
                ) : null
              )}
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="url">
            <Stack gap="md">
              <TextInput
                placeholder="Paste a link from Spotify, Apple Music, YouTube Music, or Bandcamp…"
                value={urlInput}
                onChange={(e) => {
                  setUrlInput(e.currentTarget.value)
                  setResolvedAlbum(null)
                  setShowManualFields(false)
                }}
                rightSection={resolveUrlMutation.isPending ? <Loader size="xs" /> : null}
                autoFocus
              />

              {showManualFields && (
                <Stack gap="xs">
                  <Text size="xs" c="dimmed">
                    Couldn't auto-detect album info — please enter it manually:
                  </Text>
                  <SimpleGrid cols={2} spacing="sm">
                    <TextInput
                      placeholder="Artist name"
                      value={manualArtist}
                      onChange={(e) => setManualArtist(e.currentTarget.value)}
                      size="sm"
                    />
                    <TextInput
                      placeholder="Album title"
                      value={manualAlbum}
                      onChange={(e) => setManualAlbum(e.currentTarget.value)}
                      size="sm"
                    />
                  </SimpleGrid>
                  <Button
                    size="xs"
                    variant="light"
                    color="violet"
                    disabled={!manualArtist || !manualAlbum}
                    loading={resolveUrlMutation.isPending}
                    onClick={handleManualResolve}
                  >
                    Look up album
                  </Button>
                </Stack>
              )}

              {urlError && (
                <Text size="sm" c="red.4">{urlError}</Text>
              )}

              {urlResolved && resolvedAlbum && (
                <Group justify="space-between" wrap="nowrap">
                  <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
                    <Image
                      src={resolvedAlbum.cover_url ?? undefined}
                      w={44}
                      h={44}
                      radius="sm"
                      fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='44' height='44'%3E%3Crect width='44' height='44' fill='%23373A40'/%3E%3C/svg%3E"
                    />
                    <div style={{ minWidth: 0 }}>
                      <Text size="sm" fw={500} lineClamp={1}>{resolvedAlbum.title}</Text>
                      <Text size="xs" c="dimmed" lineClamp={1}>{resolvedAlbum.artist}</Text>
                    </div>
                  </Group>
                  <Button
                    size="xs"
                    variant={urlNominated ? 'filled' : 'light'}
                    color={urlNominated ? 'green' : 'violet'}
                    disabled={urlNominated || !effectiveGroupId}
                    loading={nominateFromPool.isPending}
                    onClick={handleNominateResolved}
                    style={{ flexShrink: 0 }}
                  >
                    {urlNominated ? 'Nominated' : 'Nominate'}
                  </Button>
                </Group>
              )}

              {!urlInput && (
                <Text size="xs" c="dimmed">
                  Supported: Spotify, Apple Music, YouTube Music, Bandcamp
                </Text>
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
                          fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2020/svg' width='44' height='44'%3E%3Crect width='44' height='44' fill='%23373A40'/%3E%3C/svg%3E"
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
