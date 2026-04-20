import { useParams } from 'react-router-dom'
import { Carousel } from '@mantine/carousel'
import { Center, Divider, Paper, Skeleton, Stack, Text, Title } from '@mantine/core'
import AppShell from '../components/layout/AppShell'
import AlbumCard from '../components/spin/AlbumCard'
import ReviewForm from '../components/spin/ReviewForm'
import GuessForm from '../components/spin/GuessForm'
import GuessResult from '../components/spin/GuessResult'
import { useTodaysAlbums, useMyReview, useMyGuess } from '../hooks/useDailySpin'

function SpinSlide({ groupAlbumId, groupId }: { groupAlbumId: number; groupId: number }) {
  const { data: todaysAlbums } = useTodaysAlbums(groupId)
  const groupAlbum = todaysAlbums?.find((a) => a.id === groupAlbumId)
  const { data: review, isLoading: reviewLoading } = useMyReview(groupAlbum?.album_id ?? 0)
  const { data: guess, isLoading: guessLoading } = useMyGuess(groupId, groupAlbumId)

  if (!groupAlbum) return null

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
          <GuessForm groupId={groupId} groupAlbumId={groupAlbumId} />
        )}
      </Stack>
    </Paper>
  )
}

export default function DailySpinPage() {
  const { groupId } = useParams<{ groupId: string }>()
  const gid = Number(groupId)
  const { data: albums, isLoading } = useTodaysAlbums(gid)

  return (
    <AppShell>
      <Stack gap="lg">
        <Title order={3}>Today&apos;s Spin</Title>

        {isLoading ? (
          <Skeleton h={400} radius="md" />
        ) : albums?.length === 0 ? (
          <Center py="xl">
            <Text c="dimmed">No album selected for today yet.</Text>
          </Center>
        ) : albums?.length === 1 ? (
          <SpinSlide groupAlbumId={albums[0].id} groupId={gid} />
        ) : (
          <Carousel withIndicators loop>
            {albums?.map((a) => (
              <Carousel.Slide key={a.id}>
                <SpinSlide groupAlbumId={a.id} groupId={gid} />
              </Carousel.Slide>
            ))}
          </Carousel>
        )}
      </Stack>
    </AppShell>
  )
}
