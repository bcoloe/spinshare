import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Carousel } from '@mantine/carousel'
import {
  Alert,
  Button,
  Center,
  Divider,
  Group,
  Image,
  Paper,
  Skeleton,
  Stack,
  Text,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { IconInfoCircle, IconMusic, IconPlus } from '@tabler/icons-react'
import AlbumCard from './AlbumCard'
import SpotifyPlayer from './SpotifyPlayer'
import ReviewAndGuessForm from './ReviewAndGuessForm'
import AlbumSearchModal from '../albums/AlbumSearchModal'
import { useTodaysAlbums } from '../../hooks/useDailySpin'
import { useGroupAlbums } from '../../hooks/useAlbums'
import { useMyStats } from '../../hooks/useStats'
import { albumSearchService } from '../../services/albumSearchService'
import { ApiError } from '../../services/apiClient'
import type { GroupAlbumResponse } from '../../types/album'
import type { GroupDetailResponse } from '../../types/group'

function SpinSlide({ groupAlbum, groupId, hasSpotify }: { groupAlbum: GroupAlbumResponse; groupId: number; hasSpotify: boolean }) {
  const spotifyId = groupAlbum.album.spotify_album_id
  return (
    <Paper p="lg" radius="md" withBorder>
      <Stack gap="xl">
        <AlbumCard album={groupAlbum.album} />
        {spotifyId && (
          <SpotifyPlayer spotifyAlbumId={spotifyId} hasSpotify={hasSpotify} />
        )}
        <Divider />
        <ReviewAndGuessForm
          albumId={groupAlbum.album_id}
          groupId={groupId}
          groupAlbumId={groupAlbum.id}
          addedBy={groupAlbum.added_by}
        />
      </Stack>
    </Paper>
  )
}

function SelectTodayPanel({ groupId }: { groupId: number }) {
  const qc = useQueryClient()
  const { data: pending, isLoading } = useGroupAlbums(groupId, 'pending')
  const [selecting, setSelecting] = useState<number | null>(null)

  const handleSelect = async (groupAlbumId: number, title: string) => {
    setSelecting(groupAlbumId)
    try {
      await albumSearchService.updateStatus(groupId, groupAlbumId, 'selected')
      await qc.invalidateQueries({ queryKey: ['groups', groupId, 'albums', 'today'] })
      notifications.show({ color: 'green', message: `"${title}" selected as today's spin` })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not select album'
      notifications.show({ color: 'red', message })
    } finally {
      setSelecting(null)
    }
  }

  if (isLoading) return <Skeleton h={200} radius="md" />

  if (!pending?.length) return null

  return (
    <Stack gap="sm">
      {pending.map((ga) => (
        <Paper key={ga.id} p="sm" withBorder radius="md">
          <Group justify="space-between" wrap="nowrap">
            <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
              <Image
                src={ga.album.cover_url ?? undefined}
                w={44}
                h={44}
                radius="sm"
                fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='44' height='44'%3E%3Crect width='44' height='44' fill='%23373A40'/%3E%3C/svg%3E"
              />
              <div style={{ minWidth: 0 }}>
                <Text size="sm" fw={500} lineClamp={1}>{ga.album.title}</Text>
                <Text size="xs" c="dimmed" lineClamp={1}>{ga.album.artist}</Text>
              </div>
            </Group>
            <Button
              size="xs"
              variant="light"
              leftSection={<IconMusic size={14} />}
              loading={selecting === ga.id}
              onClick={() => handleSelect(ga.id, ga.album.title)}
              style={{ flexShrink: 0 }}
            >
              Select
            </Button>
          </Group>
        </Paper>
      ))}
    </Stack>
  )
}

interface Props {
  groupId: number
  group: GroupDetailResponse | undefined
}

export default function TodaysSpin({ groupId, group }: Props) {
  const { data: albums, isLoading, isError } = useTodaysAlbums(groupId)
  const { data: stats } = useMyStats()
  const hasSpotify = stats?.has_spotify ?? false
  const [nominateOpened, { open: openNominate, close: closeNominate }] = useDisclosure()

  const canSelect =
    group?.current_user_role === 'owner' || group?.current_user_role === 'admin'

  const isEmpty = !isLoading && !isError && albums?.length === 0

  if (isLoading) return <Skeleton h={400} radius="md" />

  if (isError) {
    return (
      <Alert color="red" title="Could not load today's spin">
        Something went wrong fetching today&apos;s album. Try refreshing.
      </Alert>
    )
  }

  if (isEmpty) {
    return (
      <>
        <Stack gap="md">
          <Alert icon={<IconInfoCircle size={16} />} color="blue" title="No spin selected yet">
            {canSelect
              ? "No album has been selected for today. Pick one from the pending nominations below, or nominate a new one."
              : "No album has been selected for today yet. Check back later or ask a group admin to select one."}
          </Alert>
          <Center>
            <Button
              variant="light"
              leftSection={<IconPlus size={16} />}
              onClick={openNominate}
            >
              Nominate an album
            </Button>
          </Center>
          {canSelect && (
            <Center>
              <Stack gap="md" w="100%" maw={560}>
                <SelectTodayPanel groupId={groupId} />
              </Stack>
            </Center>
          )}
        </Stack>
        <AlbumSearchModal groupId={groupId} opened={nominateOpened} onClose={closeNominate} />
      </>
    )
  }

  if (albums?.length === 1) {
    return <SpinSlide groupAlbum={albums[0]} groupId={groupId} hasSpotify={hasSpotify} />
  }

  return (
    <Carousel withIndicators loop>
      {albums?.map((a) => (
        <Carousel.Slide key={a.id}>
          <SpinSlide groupAlbum={a} groupId={groupId} hasSpotify={hasSpotify} />
        </Carousel.Slide>
      ))}
    </Carousel>
  )
}
