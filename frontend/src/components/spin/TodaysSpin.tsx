import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
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
  Tabs,
  Text,
  ThemeIcon,
  Tooltip,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { IconCheck, IconDice5, IconInfoCircle, IconMusic, IconPlus } from '@tabler/icons-react'
import AlbumCard from './AlbumCard'
import SpotifyPlayer from './SpotifyPlayer'
import ReviewAndGuessForm from './ReviewAndGuessForm'
import AlbumSearchModal from '../albums/AlbumSearchModal'
import { useMyReview, useTodaysAlbums, useTriggerDailySelection } from '../../hooks/useDailySpin'
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

function AlbumTab({ albumId, title, coverUrl }: { albumId: number; title: string; coverUrl: string | null }) {
  const { data: review } = useMyReview(albumId)
  const reviewed = !!review
  return (
    <Tooltip label={title} openDelay={400} disabled={title.length <= 22}>
      <Group gap={6} wrap="nowrap">
        <Image
          src={coverUrl ?? undefined}
          w={20}
          h={20}
          radius="xs"
          fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='20' height='20'%3E%3Crect width='20' height='20' fill='%23373A40'/%3E%3C/svg%3E"
        />
        <Text size="sm" lineClamp={1} style={{ maxWidth: 110 }}>
          {title}
        </Text>
        {reviewed && (
          <ThemeIcon size={14} radius="xl" color="green" variant="filled">
            <IconCheck size={9} />
          </ThemeIcon>
        )}
      </Group>
    </Tooltip>
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
  const [activeAlbumValue, setActiveAlbumValue] = useState<string | null>(null)
  const triggerSelection = useTriggerDailySelection(groupId)

  const canSelect =
    group?.current_user_role === 'owner' || group?.current_user_role === 'admin'

  const isEmpty = !isLoading && !isError && albums?.length === 0

  const handleRollSpin = async () => {
    try {
      await triggerSelection.mutateAsync()
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not select albums'
      notifications.show({ color: 'red', message })
    }
  }

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
            No album has been selected for today yet. Roll a random spin or nominate a new one.
          </Alert>
          <Center>
            <Group gap="sm">
              <Button
                variant="filled"
                leftSection={<IconDice5 size={16} />}
                loading={triggerSelection.isPending}
                onClick={handleRollSpin}
              >
                Roll today&apos;s spin
              </Button>
              <Button
                variant="light"
                leftSection={<IconPlus size={16} />}
                onClick={openNominate}
              >
                Nominate an album
              </Button>
            </Group>
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

  const definedAlbums = albums!
  const currentValue = activeAlbumValue ?? String(definedAlbums[0].id)
  const activeAlbum = definedAlbums.find((a) => String(a.id) === currentValue) ?? definedAlbums[0]

  return (
    <Stack gap="md">
      <Tabs value={currentValue} onChange={setActiveAlbumValue}>
        <Tabs.List>
          {definedAlbums.map((a) => (
            <Tabs.Tab key={a.id} value={String(a.id)}>
              <AlbumTab albumId={a.album_id} title={a.album.title} coverUrl={a.album.cover_url} />
            </Tabs.Tab>
          ))}
        </Tabs.List>
      </Tabs>
      <SpinSlide key={activeAlbum.id} groupAlbum={activeAlbum} groupId={groupId} hasSpotify={hasSpotify} />
    </Stack>
  )
}
