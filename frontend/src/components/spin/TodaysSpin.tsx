import { useState, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  Alert,
  Anchor,
  Badge,
  Box,
  Button,
  Center,
  Divider,
  Group,
  Image,
  Modal,
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
import { IconBrandApple, IconBrandSpotify, IconBrandYoutube, IconCheck, IconClock, IconDice5, IconExternalLink, IconHistory, IconInfoCircle, IconMusic, IconPlus } from '@tabler/icons-react'
import AlbumCard from './AlbumCard'
import ReviewAndGuessForm from './ReviewAndGuessForm'
import AlbumSearchModal from '../albums/AlbumSearchModal'
import { usePlayer } from '../../context/PlayerContext'
import { useCatchUpAlbums, useMyReview, useTodaysAlbums, useTriggerDailySelection } from '../../hooks/useDailySpin'
import { useGroupAlbums, useNominationCount } from '../../hooks/useAlbums'
import { albumSearchService } from '../../services/albumSearchService'
import { ApiError } from '../../services/apiClient'
import type { GroupAlbumResponse } from '../../types/album'
import type { GroupDetailResponse } from '../../types/group'

// ==================== NEXT DRAW HELPERS ====================

const WEEKDAY_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const WEEKDAY_FULL = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

function getNextDrawInfo(
  timezone: string,
  selectionDays: number[],
): { isToday: boolean; label: string | null } {
  if (!selectionDays.length) return { isToday: false, label: null }
  try {
    const now = new Date()
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      weekday: 'short',
      hour: 'numeric',
      minute: 'numeric',
      hourCycle: 'h23',
    }).formatToParts(now)
    const weekdayStr = parts.find(p => p.type === 'weekday')?.value ?? ''
    const hour = parseInt(parts.find(p => p.type === 'hour')?.value ?? '0', 10)
    const minute = parseInt(parts.find(p => p.type === 'minute')?.value ?? '0', 10)
    const todayIdx = WEEKDAY_SHORT.indexOf(weekdayStr)
    if (todayIdx === -1) return { isToday: false, label: null }

    const isToday = selectionDays.includes(todayIdx)

    // Minimum days ahead (>0) until next scheduled draw — wraps week if today is a draw day
    let daysAhead = Infinity
    for (const d of selectionDays) {
      const diff = ((d - todayIdx + 7) % 7) || 7  // 1..7
      if (diff < daysAhead) daysAhead = diff
    }
    if (!isFinite(daysAhead)) return { isToday, label: null }

    const minutesUntilMidnight = (23 - hour) * 60 + (60 - minute)
    const totalHours = Math.round(minutesUntilMidnight / 60) + (daysAhead - 1) * 24
    const targetDayIdx = (todayIdx + daysAhead) % 7

    let label: string
    if (totalHours < 1) {
      label = 'Next draw in less than an hour'
    } else if (totalHours < 24) {
      label = `Next draw in ${totalHours} hour${totalHours !== 1 ? 's' : ''}`
    } else if (daysAhead === 1) {
      label = `Next draw tomorrow (${WEEKDAY_FULL[targetDayIdx]})`
    } else {
      label = `Next draw in ${daysAhead} days (${WEEKDAY_FULL[targetDayIdx]})`
    }
    return { isToday, label }
  } catch {
    return { isToday: false, label: null }
  }
}

// ==================== SPIN COMPONENTS ====================

function SpinSlide({ groupAlbum, groupId, allowGuessing = true }: { groupAlbum: GroupAlbumResponse; groupId: number; allowGuessing?: boolean }) {
  const spotifyId = groupAlbum.album.spotify_album_id
  const appleMusicId = groupAlbum.album.apple_music_album_id
  const { startAlbum, playInAppleMusic, hasSpotify, hasAppleMusic, preferredService, status: playerStatus } = usePlayer()
  const canPlaySpotify = hasSpotify && !!spotifyId
  const canPlayAppleMusic = hasAppleMusic && !!appleMusicId
  const effectivePlayService: 'spotify' | 'apple_music' = (() => {
    if (preferredService === 'apple_music' && canPlayAppleMusic) return 'apple_music'
    if (preferredService === 'spotify' && canPlaySpotify) return 'spotify'
    if (canPlaySpotify) return 'spotify'
    if (canPlayAppleMusic) return 'apple_music'
    return preferredService
  })()
  const canPlay = effectivePlayService === 'apple_music' ? canPlayAppleMusic : canPlaySpotify
  const playMeta = {
    spotifyAlbumId: spotifyId,
    appleMusicAlbumId: appleMusicId,
    title: groupAlbum.album.title,
    artist: groupAlbum.album.artist,
    coverUrl: groupAlbum.album.cover_url ?? null,
    appAlbumId: groupAlbum.album_id,
    groupId,
    groupAlbumId: groupAlbum.id,
  }
  const handlePlay = () => effectivePlayService === 'apple_music'
    ? playInAppleMusic(playMeta)
    : startAlbum(spotifyId!, playMeta)
  return (
    <Paper p="lg" radius="md" withBorder>
      <Stack gap="xl">
        <AlbumCard album={groupAlbum.album} />
        <Stack gap={4}>
          <Group gap="sm" wrap="wrap">
            <Button
              variant="filled"
              color={effectivePlayService === 'apple_music' ? 'red' : 'green'}
              size="sm"
              leftSection={effectivePlayService === 'apple_music'
                ? <IconBrandApple size={16} />
                : <IconBrandSpotify size={16} />}
              loading={playerStatus === 'loading'}
              disabled={!canPlay}
              onClick={handlePlay}
            >
              Play
            </Button>
            <Tooltip label="Not found on Spotify" disabled={!!spotifyId}>
              <Button
                component="a"
                href={spotifyId ? `spotify:album:${spotifyId}` : undefined}
                variant="light"
                color="green"
                size="sm"
                leftSection={<IconBrandSpotify size={16} />}
                disabled={!spotifyId}
              >
                Open in Spotify
              </Button>
            </Tooltip>
            <Tooltip label="Not found on Spotify" disabled={!!spotifyId}>
              <Button
                component="a"
                href={spotifyId ? `https://open.spotify.com/album/${spotifyId}` : undefined}
                target="_blank"
                rel="noopener noreferrer"
                variant="subtle"
                size="sm"
                leftSection={<IconExternalLink size={16} />}
                disabled={!spotifyId}
              >
                Web Player
              </Button>
            </Tooltip>
            {groupAlbum.album.youtube_music_id && (
              <Button
                component="a"
                href={`https://music.youtube.com/browse/${groupAlbum.album.youtube_music_id}`}
                target="_blank"
                rel="noopener noreferrer"
                variant="subtle"
                size="sm"
                leftSection={<IconBrandYoutube size={16} />}
              >
                YouTube Music
              </Button>
            )}
            {groupAlbum.album.artist_url && (
              <Button
                component="a"
                href={groupAlbum.album.artist_url}
                target="_blank"
                rel="noopener noreferrer"
                variant="subtle"
                size="sm"
                leftSection={<IconExternalLink size={16} />}
              >
                Open URL
              </Button>
            )}
            <Tooltip label="Not found on Apple Music" disabled={!!appleMusicId}>
              <Button
                component="a"
                href={appleMusicId ? `https://music.apple.com/album/${appleMusicId}` : undefined}
                target="_blank"
                rel="noopener noreferrer"
                variant="light"
                color="red"
                size="sm"
                leftSection={<IconBrandApple size={16} />}
                disabled={!appleMusicId}
              >
                Open in Apple Music
              </Button>
            </Tooltip>
          </Group>
          {!hasSpotify && !hasAppleMusic && (
            <Text size="xs" c="dimmed">
              <Anchor component={Link} to="/profile" size="xs">Connect Spotify or Apple Music</Anchor> on your profile to enable the embedded player
            </Text>
          )}
        </Stack>
        <Divider />
        <ReviewAndGuessForm
          albumId={groupAlbum.album_id}
          groupId={groupId}
          groupAlbumId={groupAlbum.id}
          addedBy={groupAlbum.added_by}
          allowGuessing={allowGuessing}
        />
      </Stack>
    </Paper>
  )
}

function MultiAlbumSpin({ albums, groupId, allowGuessing = true }: { albums: GroupAlbumResponse[]; groupId: number; allowGuessing?: boolean }) {
  const [searchParams] = useSearchParams()
  const [activeAlbumValue, setActiveAlbumValue] = useState<string | null>(searchParams.get('album'))
  const { startAlbum, playInAppleMusic, hasSpotify, hasAppleMusic, preferredService, status: playerStatus, playingSpotifyAlbumId } = usePlayer()

  useEffect(() => {
    const album = searchParams.get('album')
    if (album) setActiveAlbumValue(album)
  }, [searchParams])
  const currentValue = activeAlbumValue ?? String(albums[0].id)
  const activeAlbum = albums.find((a) => String(a.id) === currentValue) ?? albums[0]
  const spotifyId = activeAlbum.album.spotify_album_id
  const appleMusicId = activeAlbum.album.apple_music_album_id
  const canPlaySpotify = hasSpotify && !!spotifyId
  const canPlayAppleMusic = hasAppleMusic && !!appleMusicId
  const effectivePlayService: 'spotify' | 'apple_music' = (() => {
    if (preferredService === 'apple_music' && canPlayAppleMusic) return 'apple_music'
    if (preferredService === 'spotify' && canPlaySpotify) return 'spotify'
    if (canPlaySpotify) return 'spotify'
    if (canPlayAppleMusic) return 'apple_music'
    return preferredService
  })()
  const canPlay = effectivePlayService === 'apple_music' ? canPlayAppleMusic : canPlaySpotify
  const playMeta = {
    spotifyAlbumId: spotifyId,
    appleMusicAlbumId: appleMusicId,
    title: activeAlbum.album.title,
    artist: activeAlbum.album.artist,
    coverUrl: activeAlbum.album.cover_url ?? null,
    appAlbumId: activeAlbum.album_id,
    groupId,
    groupAlbumId: activeAlbum.id,
  }
  const handlePlay = () => effectivePlayService === 'apple_music'
    ? playInAppleMusic(playMeta)
    : startAlbum(spotifyId!, playMeta)

  return (
    <Stack gap="md">
      <Tabs value={currentValue} onChange={setActiveAlbumValue}>
        <Tabs.List>
          {albums.map((a) => (
            <Tabs.Tab key={a.id} value={String(a.id)}>
              <AlbumTab
                albumId={a.album_id}
                title={a.album.title}
                coverUrl={a.album.cover_url}
                isPlaying={!!a.album.spotify_album_id && a.album.spotify_album_id === playingSpotifyAlbumId}
              />
            </Tabs.Tab>
          ))}
        </Tabs.List>
      </Tabs>
      <Paper p="lg" radius="md" withBorder>
        <Stack gap="xl">
          <AlbumCard album={activeAlbum.album} />
          <Stack gap={4}>
            <Group gap="sm" wrap="wrap">
              <Button
                variant="filled"
                color={effectivePlayService === 'apple_music' ? 'red' : 'green'}
                size="sm"
                leftSection={effectivePlayService === 'apple_music'
                  ? <IconBrandApple size={16} />
                  : <IconBrandSpotify size={16} />}
                loading={playerStatus === 'loading'}
                disabled={!canPlay}
                onClick={handlePlay}
              >
                Play
              </Button>
              <Tooltip label="Not found on Spotify" disabled={!!spotifyId}>
                <Button
                  component="a"
                  href={spotifyId ? `spotify:album:${spotifyId}` : undefined}
                  variant="light"
                  color="green"
                  size="sm"
                  leftSection={<IconBrandSpotify size={16} />}
                  disabled={!spotifyId}
                >
                  Open in Spotify
                </Button>
              </Tooltip>
              <Tooltip label="Not found on Spotify" disabled={!!spotifyId}>
                <Button
                  component="a"
                  href={spotifyId ? `https://open.spotify.com/album/${spotifyId}` : undefined}
                  target="_blank"
                  rel="noopener noreferrer"
                  variant="subtle"
                  size="sm"
                  leftSection={<IconExternalLink size={16} />}
                  disabled={!spotifyId}
                >
                  Web Player
                </Button>
              </Tooltip>
              {activeAlbum.album.youtube_music_id && (
                <Button
                  component="a"
                  href={`https://music.youtube.com/browse/${activeAlbum.album.youtube_music_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  variant="subtle"
                  size="sm"
                  leftSection={<IconBrandYoutube size={16} />}
                >
                  YouTube Music
                </Button>
              )}
              {activeAlbum.album.artist_url && (
                <Button
                  component="a"
                  href={activeAlbum.album.artist_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  variant="subtle"
                  size="sm"
                  leftSection={<IconExternalLink size={16} />}
                >
                  Open URL
                </Button>
              )}
              <Tooltip label="Not found on Apple Music" disabled={!!appleMusicId}>
                <Button
                  component="a"
                  href={appleMusicId ? `https://music.apple.com/album/${appleMusicId}` : undefined}
                  target="_blank"
                  rel="noopener noreferrer"
                  variant="light"
                  color="red"
                  size="sm"
                  leftSection={<IconBrandApple size={16} />}
                  disabled={!appleMusicId}
                >
                  Open in Apple Music
                </Button>
              </Tooltip>
            </Group>
            {!hasSpotify && !hasAppleMusic && (
              <Text size="xs" c="dimmed">
                <Anchor component={Link} to="/profile" size="xs">Connect Spotify or Apple Music</Anchor> on your profile to enable the embedded player
              </Text>
            )}
          </Stack>
          <Divider />
          <ReviewAndGuessForm
            key={activeAlbum.id}
            albumId={activeAlbum.album_id}
            groupId={groupId}
            groupAlbumId={activeAlbum.id}
            addedBy={activeAlbum.added_by}
            allowGuessing={allowGuessing}
          />
        </Stack>
      </Paper>
    </Stack>
  )
}

function AlbumTab({ albumId, title, coverUrl, isPlaying = false }: { albumId: number; title: string; coverUrl: string | null; isPlaying?: boolean }) {
  const { data: review } = useMyReview(albumId)
  const reviewed = !!review && !review.is_draft
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
        {isPlaying && (
          <ThemeIcon size={14} radius="xl" color="green" variant="light">
            <IconMusic size={9} />
          </ThemeIcon>
        )}
        {reviewed && !isPlaying && (
          <ThemeIcon size={14} radius="xl" color="green" variant="filled">
            <IconCheck size={9} />
          </ThemeIcon>
        )}
      </Group>
    </Tooltip>
  )
}

function CatchUpSection({ albums, groupId, allowGuessing }: { albums: GroupAlbumResponse[]; groupId: number; allowGuessing: boolean }) {
  const [activeId, setActiveId] = useState<number>(albums[0]?.id)
  const activeAlbum = albums.find((a) => a.id === activeId) ?? albums[0]

  if (!albums.length) return null

  const formatDate = (iso: string) => {
    const d = new Date(iso)
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  }

  return (
    <Stack gap="md">
      <Tabs
        value={String(activeId)}
        onChange={(v) => v && setActiveId(Number(v))}
        color="teal"
      >
        <Tabs.List>
          {albums.map((a) => (
            <Tabs.Tab key={a.id} value={String(a.id)}>
              <Group gap={6} wrap="nowrap">
                <Image
                  src={a.album.cover_url ?? undefined}
                  w={20}
                  h={20}
                  radius="xs"
                  fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='20' height='20'%3E%3Crect width='20' height='20' fill='%23373A40'/%3E%3C/svg%3E"
                />
                <Stack gap={0}>
                  <Text size="sm" lineClamp={1} style={{ maxWidth: 110 }}>{a.album.title}</Text>
                  {a.selected_date && (
                    <Text size="xs" c="dimmed">{formatDate(a.selected_date)}</Text>
                  )}
                </Stack>
              </Group>
            </Tabs.Tab>
          ))}
        </Tabs.List>
      </Tabs>
      {activeAlbum && (
        <SpinSlide
          key={activeAlbum.id}
          groupAlbum={activeAlbum}
          groupId={groupId}
          allowGuessing={allowGuessing}
        />
      )}
    </Stack>
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
  const catchUpEnabled = group?.settings?.catch_up_enabled ?? false
  const { data: catchUpAlbums = [] } = useCatchUpAlbums(groupId, catchUpEnabled)
  const [spinView, setSpinView] = useState<string>('today')
  const { data: nominationCountData } = useNominationCount(groupId)
  const [nominateOpened, { open: openNominate, close: closeNominate }] = useDisclosure()
  const [chaosConfirmOpen, { open: openChaosConfirm, close: closeChaosConfirm }] = useDisclosure()
  const triggerSelection = useTriggerDailySelection(groupId)

  const allowGuessing = group?.settings?.allow_guessing ?? true
  const canSelect =
    group?.current_user_role === 'owner' || group?.current_user_role === 'admin'

  const ROLE_RANK: Record<string, number> = { owner: 0, admin: 1, member: 2 }
  const minRoleToNominate = group?.settings?.min_role_to_nominate ?? 'member'
  const canNominate =
    !!group?.current_user_role &&
    (ROLE_RANK[group.current_user_role] ?? 99) <= (ROLE_RANK[minRoleToNominate] ?? 99)

  const isEmpty = !isLoading && !isError && albums?.length === 0

  const dailyAlbumCount = group?.settings?.daily_album_count ?? 1
  const pendingCount = nominationCountData?.pending_count ?? 0
  const poolColor =
    pendingCount >= 10 * dailyAlbumCount
      ? 'green'
      : pendingCount >= 5 * dailyAlbumCount
        ? 'yellow'
        : pendingCount >= 2 * dailyAlbumCount
          ? 'orange'
          : 'red'
  const poolTooltip =
    pendingCount === 0
      ? 'Nomination pool is empty — add albums to continue daily spins!'
      : pendingCount < 2 * dailyAlbumCount
        ? 'Pool is critically low — add more nominations soon!'
        : pendingCount < 5 * dailyAlbumCount
          ? 'Pool is running low — consider adding more nominations'
          : pendingCount < 10 * dailyAlbumCount
            ? 'Pool is moderate — keep nominations coming'
            : 'Pool is healthy'
  const nextDraw = group?.settings
    ? getNextDrawInfo(group.settings.timezone, group.settings.selection_days)
    : null

  const poolBadge = nominationCountData !== undefined ? (
    <Group justify="space-between" align="center">
      {nextDraw?.label ? (
        <Group gap={4} c="dimmed">
          <IconClock size={12} />
          <Text size="xs">{nextDraw.label}</Text>
        </Group>
      ) : <span />}
      <Tooltip label={poolTooltip}>
        <Badge size="sm" color={poolColor} variant="light" style={{ cursor: 'default' }}>
          {pendingCount} nomination{pendingCount !== 1 ? 's' : ''} in pool
        </Badge>
      </Tooltip>
    </Group>
  ) : null

  const handleRollSpin = async () => {
    try {
      await triggerSelection.mutateAsync({})
    } catch (err) {
      if (err instanceof ApiError && err.message === 'no_nominations_chaos_available') {
        openChaosConfirm()
        return
      }
      const message = err instanceof ApiError ? err.message : 'Could not select albums'
      notifications.show({ color: 'red', message })
    }
  }

  const handleFullChaosConfirm = async () => {
    closeChaosConfirm()
    try {
      await triggerSelection.mutateAsync({ forceChaos: true })
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
          {poolBadge}
          <Alert
            icon={<IconInfoCircle size={16} />}
            color="blue"
            title="No spin selected yet"
          >
            No album has been selected yet. Roll a random spin or nominate a new one.
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
              <Tooltip
                label="You don't have permission to nominate albums in this group"
                disabled={canNominate}
              >
                <Box component="span" style={canNominate ? undefined : { cursor: 'not-allowed' }}>
                  <Button
                    variant="light"
                    leftSection={<IconPlus size={16} />}
                    onClick={openNominate}
                    disabled={!canNominate}
                    style={canNominate ? undefined : { pointerEvents: 'none' }}
                  >
                    Nominate an album
                  </Button>
                </Box>
              </Tooltip>
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
        <Modal opened={chaosConfirmOpen} onClose={closeChaosConfirm} title="⚡ Full Chaos Mode">
          <Stack gap="md">
            <Text size="sm">
              There are no active nominations in the pool. Since chaos mode is enabled, today&apos;s
              spin can be pulled entirely from random albums outside the group.
            </Text>
            <Text size="sm" c="dimmed">
              Are you ready to embrace the chaos?
            </Text>
            <Group justify="flex-end">
              <Button variant="default" onClick={closeChaosConfirm}>Cancel</Button>
              <Button
                color="orange"
                leftSection={<IconDice5 size={16} />}
                loading={triggerSelection.isPending}
                onClick={handleFullChaosConfirm}
              >
                Go full chaos
              </Button>
            </Group>
          </Stack>
        </Modal>
      </>
    )
  }

  const hasCatchUp = catchUpEnabled && catchUpAlbums.length > 0

  const todayContent = albums?.length === 1
    ? <SpinSlide key={albums[0].album_id} groupAlbum={albums[0]} groupId={groupId} allowGuessing={allowGuessing} />
    : <MultiAlbumSpin albums={albums!} groupId={groupId} allowGuessing={allowGuessing} />

  if (!hasCatchUp) {
    return (
      <Stack gap="md">
        {poolBadge}
        {todayContent}
      </Stack>
    )
  }

  return (
    <Stack gap="md">
      {poolBadge}
      <Tabs value={spinView} onChange={(v) => v && setSpinView(v)}>
        <Tabs.List>
          <Tabs.Tab value="today" color="yellow" leftSection={<IconClock size={14} />}>
            Today's Spin
          </Tabs.Tab>
          <Tabs.Tab value="catchup" color="teal" leftSection={<IconHistory size={14} />}>
            Catch Up
            <Badge ml={6} size="xs" color="teal" variant="light" circle>
              {catchUpAlbums.length}
            </Badge>
          </Tabs.Tab>
        </Tabs.List>
      </Tabs>
      {spinView === 'today' ? todayContent : (
        <CatchUpSection albums={catchUpAlbums} groupId={groupId} allowGuessing={allowGuessing} />
      )}
    </Stack>
  )
}
