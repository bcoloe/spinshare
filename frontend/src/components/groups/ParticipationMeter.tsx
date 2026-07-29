import { useMemo } from 'react'
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
  Tooltip,
  UnstyledButton,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { IconBolt } from '@tabler/icons-react'

import { useGroupAlbums } from '../../hooks/useAlbums'
import { useParticipation, useSetPriorityPick } from '../../hooks/useGroups'
import { useAuth } from '../../hooks/useAuth'
import { ApiError } from '../../services/apiClient'
import type { GroupAlbumResponse } from '../../types/album'

interface Props {
  groupId: number
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
  const [opened, { open, close }] = useDisclosure(false)

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

  // Feature disabled for this group (global/dealer/unset) — render nothing.
  if (!participation || participation.threshold == null) return null

  const { threshold, credits, can_pick, pending_pick } = participation
  const pct = Math.min(100, Math.round((credits / threshold) * 100))

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
          <Group justify="space-between" align="center" mt={4}>
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
            <Badge color="yellow" variant="light" leftSection={<IconBolt size={12} />}>
              Next up
            </Badge>
          </Group>
        ) : can_pick ? (
          <Tooltip
            label={myPending.length === 0 ? 'Nominate an album first' : 'Send a nomination to the front of the line'}
          >
            <Button
              size="xs"
              variant="filled"
              color="orange.7"
              mt={4}
              onClick={open}
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
          The album you choose jumps to the front of the next daily draw. This uses up your priority
          pick — you can promote another once it's drawn.
        </Text>
        <ScrollArea.Autosize mah={360}>
          <Stack gap="xs">
            {myPending.map((ga) => (
              <UnstyledButton
                key={ga.id}
                onClick={() => handlePick(ga)}
                disabled={setPriorityPick.isPending}
              >
                <Card withBorder radius="sm" padding="xs">
                  <Group gap="sm">
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
                </Card>
              </UnstyledButton>
            ))}
          </Stack>
        </ScrollArea.Autosize>
      </Modal>
    </Card>
  )
}
