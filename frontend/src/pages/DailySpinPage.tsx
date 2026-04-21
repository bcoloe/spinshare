import { useState } from 'react'
import { useParams } from 'react-router-dom'
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
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconInfoCircle, IconMusic } from '@tabler/icons-react'
import AppShell from '../components/layout/AppShell'
import AlbumCard from '../components/spin/AlbumCard'
import ReviewForm from '../components/spin/ReviewForm'
import GuessForm from '../components/spin/GuessForm'
import GuessResult from '../components/spin/GuessResult'
import { useTodaysAlbums, useMyReview, useMyGuess } from '../hooks/useDailySpin'
import { useGroupAlbums } from '../hooks/useAlbums'
import { useGroup } from '../hooks/useGroups'
import { albumSearchService } from '../services/albumSearchService'
import { ApiError } from '../services/apiClient'
import { useQueryClient } from '@tanstack/react-query'
import type { GroupAlbumResponse } from '../types/album'

function SpinSlide({ groupAlbum, groupId }: { groupAlbum: GroupAlbumResponse; groupId: number }) {
  const { data: review, isLoading: reviewLoading } = useMyReview(groupAlbum.album_id)
  const { data: guess, isLoading: guessLoading } = useMyGuess(groupId, groupAlbum.id)

  return (
    <Paper p="lg" radius="md" withBorder>
      <Stack gap="xl">
        <AlbumCard album={groupAlbum.album} />
        <Divider />
        {reviewLoading ? (
          <Skeleton h={100} />
        ) : (
          <ReviewForm albumId={groupAlbum.album_id} existingReview={review ?? null} />
        )}
        <Divider />
        {guessLoading ? (
          <Skeleton h={80} />
        ) : guess ? (
          <GuessResult result={guess} />
        ) : (
          <GuessForm groupId={groupId} groupAlbumId={groupAlbum.id} />
        )}
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

  if (!pending?.length) {
    return (
      <Alert icon={<IconInfoCircle size={16} />} color="gray">
        No albums have been nominated yet. Go to the group catalog to nominate some.
      </Alert>
    )
  }

  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed">Choose an album from the group&apos;s pending nominations:</Text>
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

export default function DailySpinPage() {
  const { groupId } = useParams<{ groupId: string }>()
  const gid = Number(groupId)
  const { data: albums, isLoading, isError } = useTodaysAlbums(gid)
  const { data: group } = useGroup(gid)

  const canSelect =
    group?.current_user_role === 'owner' || group?.current_user_role === 'admin'

  const isEmpty = !isLoading && !isError && albums?.length === 0

  return (
    <AppShell>
      <Stack gap="lg">
        <Title order={3}>Today&apos;s Spin</Title>

        {isLoading ? (
          <Skeleton h={400} radius="md" />
        ) : isError ? (
          <Alert color="red" title="Could not load today's spin">
            Something went wrong fetching today&apos;s album. Try refreshing.
          </Alert>
        ) : isEmpty ? (
          <Stack gap="md">
            <Alert icon={<IconInfoCircle size={16} />} color="blue" title="No spin selected yet">
              {canSelect
                ? "No album has been selected for today. Pick one from the nominations below."
                : "No album has been selected for today yet. Check back later or ask a group admin to select one."}
            </Alert>
            {canSelect && (
              <Center>
                <Stack gap="md" w="100%" maw={560}>
                  <SelectTodayPanel groupId={gid} />
                </Stack>
              </Center>
            )}
          </Stack>
        ) : albums?.length === 1 ? (
          <SpinSlide groupAlbum={albums[0]} groupId={gid} />
        ) : (
          <Carousel withIndicators loop>
            {albums?.map((a) => (
              <Carousel.Slide key={a.id}>
                <SpinSlide groupAlbum={a} groupId={gid} />
              </Carousel.Slide>
            ))}
          </Carousel>
        )}
      </Stack>
    </AppShell>
  )
}
