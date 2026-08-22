import { useMemo, useState } from 'react'
import {
  Badge,
  Button,
  Card,
  Group,
  Image,
  Modal,
  Progress,
  ScrollArea,
  Stack,
  Text,
  TextInput,
  Tooltip,
  UnstyledButton,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { IconBolt, IconSearch } from '@tabler/icons-react'

import { useGroupAlbums } from '../../hooks/useAlbums'
import {
  useClearPriorityPick,
  useParticipation,
  useSetPriorityPick,
} from '../../hooks/useGroups'
import { useAuth } from '../../hooks/useAuth'
import { ApiError } from '../../services/apiClient'
import type { GroupAlbumResponse } from '../../types/album'

interface Props {
  groupId: number
}

/** Format a 1-based queue place as an ordinal, e.g. 2 → "2nd", 3 → "3rd". */
function ordinal(n: number): string {
  const mod100 = n % 100
  if (mod100 >= 11 && mod100 <= 13) return `${n}th`
  switch (n % 10) {
    case 1:
      return `${n}st`
    case 2:
      return `${n}nd`
    case 3:
      return `${n}rd`
    default:
      return `${n}th`
  }
}

/**
 * Bottom-of-group-page participation meter. Fills as the member publishes
 * reviews; once full they may promote one of their pending nominations to the
 * front of the daily draw. A promoted pick is shown as "Next up" and stays
 * locked until the next draw renders it.
 */
export default function ParticipationMeter({ groupId }: Props) {
  const { user } = useAuth()
  const { data: participation } = useParticipation(groupId)
  const { data: allAlbums = [] } = useGroupAlbums(groupId)
  const setPriorityPick = useSetPriorityPick(groupId)
  const clearPriorityPick = useClearPriorityPick(groupId)
  const [opened, { open, close }] = useDisclosure(false)
  const [query, setQuery] = useState('')

  const openPicker = () => {
    setQuery('')
    open()
  }

  const myPending = useMemo(
    () =>
      allAlbums.filter(
        (ga) =>
          ga.status === 'pending' &&
          user?.id !== undefined &&
          ga.nominator_user_ids.includes(user.id),
      ),
    [allAlbums, user],
  )

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return myPending
    return myPending.filter(
      (ga) =>
        ga.album.title.toLowerCase().includes(needle) ||
        ga.album.artist.toLowerCase().includes(needle),
    )
  }, [myPending, query])

  // Feature disabled for this group (global/dealer/unset) — render nothing.
  if (!participation || participation.threshold == null) return null

  const { threshold, credits, can_pick, pending_pick, queue_position, queue_size } = participation
  const pct = Math.min(100, Math.round((credits / threshold) * 100))
  const isNext = queue_position === 1

  const handlePick = async (ga: GroupAlbumResponse) => {
    try {
      await setPriorityPick.mutateAsync(ga.id)
      close()
      notifications.show({
        color: 'green',
        message: `"${ga.album.title}" is next up on the draw`,
      })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not promote nomination'
      notifications.show({ color: 'red', message })
    }
  }

  const handleCancel = async () => {
    try {
      await clearPriorityPick.mutateAsync()
      notifications.show({ color: 'gray', message: 'Priority pick cancelled' })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not cancel priority pick'
      notifications.show({ color: 'red', message })
    }
  }

  return (
    <Card withBorder radius="md" padding="md">
      <Stack gap="xs">
        <Group justify="space-between" align="center">
          <Group gap={6}>
            <IconBolt size={18} />
            <Text fw={600} size="sm">
              Priority pick
            </Text>
          </Group>
          <Text size="sm" c="dimmed">
            {credits} / {threshold} reviews
          </Text>
        </Group>

        <Progress value={pct} radius="xl" size="lg" color="yellow.6" />

        {pending_pick ? (
          <Stack gap={6} mt={4}>
            <Group justify="space-between" align="center">
              <Group gap="sm">
                <Image
                  src={pending_pick.album.cover_url}
                  w={36}
                  h={36}
                  radius="sm"
                  alt={pending_pick.album.title}
                />
                <div>
                  <Text size="sm" fw={500} lineClamp={1}>
                    {pending_pick.album.title}
                  </Text>
                  <Text size="xs" c="dimmed" lineClamp={1}>
                    {pending_pick.album.artist}
                  </Text>
                </div>
              </Group>
              <Tooltip
                multiline
                w={220}
                label={
                  isNext
                    ? 'First in line — drawn on the next spin. Change or cancel until then.'
                    : `${ordinal(queue_position ?? 0)} of ${queue_size} in the priority queue. Picks are drawn in order; changing your album keeps your place.`
                }
              >
                <Badge
                  color={isNext ? 'yellow' : 'gray'}
                  variant="light"
                  leftSection={<IconBolt size={12} />}
                >
                  {isNext ? 'Next up' : `${ordinal(queue_position ?? 0)} in queue`}
                </Badge>
              </Tooltip>
            </Group>
            <Group gap="xs">
              <Button
                size="compact-xs"
                variant="default"
                onClick={openPicker}
                disabled={myPending.length <= 1 || clearPriorityPick.isPending}
              >
                Change
              </Button>
              <Button
                size="compact-xs"
                variant="subtle"
                color="red"
                onClick={handleCancel}
                loading={clearPriorityPick.isPending}
              >
                Cancel
              </Button>
            </Group>
          </Stack>
        ) : can_pick ? (
          <Tooltip
            label={myPending.length === 0 ? 'Nominate an album first' : 'Send a nomination to the front of the line'}
          >
            <Button
              size="xs"
              variant="filled"
              color="orange.7"
              mt={4}
              onClick={openPicker}
              disabled={myPending.length === 0}
            >
              Choose priority album
            </Button>
          </Tooltip>
        ) : (
          <Text size="xs" c="dimmed">
            Publish {threshold - credits} more review{threshold - credits === 1 ? '' : 's'} to unlock a
            priority pick.
          </Text>
        )}
      </Stack>

      <Modal opened={opened} onClose={close} title="Promote a nomination" centered>
        <Text size="sm" c="dimmed" mb="sm">
          The album you choose jumps to the front of the next daily draw. Nothing is spent until it
          is drawn, so you can change or cancel your pick any time before then.
        </Text>
        <TextInput
          mb="sm"
          placeholder="Filter by album or artist"
          leftSection={<IconSearch size={16} />}
          value={query}
          onChange={(event) => setQuery(event.currentTarget.value)}
          aria-label="Filter nominations"
        />
        <ScrollArea.Autosize mah={360}>
          <Stack gap="xs">
            {filtered.length === 0 && (
              <Text size="sm" c="dimmed" ta="center" py="md">
                No nominations match "{query.trim()}"
              </Text>
            )}
            {filtered.map((ga) => {
              // Co-nominated albums are listed under the earliest nominator's row, so
              // the queued pick (always the caller's own row) is matched by album.
              const isCurrent = ga.album_id === pending_pick?.album_id
              return (
                <UnstyledButton
                  key={ga.id}
                  onClick={() => handlePick(ga)}
                  disabled={setPriorityPick.isPending || isCurrent}
                >
                  <Card withBorder radius="sm" padding="xs">
                    <Group gap="sm" justify="space-between">
                      <Group gap="sm" style={{ minWidth: 0 }}>
                        <Image src={ga.album.cover_url} w={40} h={40} radius="sm" alt={ga.album.title} />
                        <div style={{ minWidth: 0 }}>
                          <Text size="sm" fw={500} lineClamp={1}>
                            {ga.album.title}
                          </Text>
                          <Text size="xs" c="dimmed" lineClamp={1}>
                            {ga.album.artist}
                          </Text>
                        </div>
                      </Group>
                      {isCurrent && (
                        <Badge color="yellow" variant="light" size="sm">
                          Current
                        </Badge>
                      )}
                    </Group>
                  </Card>
                </UnstyledButton>
              )
            })}
          </Stack>
        </ScrollArea.Autosize>
      </Modal>
    </Card>
  )
}
