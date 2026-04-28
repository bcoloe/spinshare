import { useMemo, useState } from 'react'
import {
  Badge,
  Button,
  Checkbox,
  Group,
  Image,
  Modal,
  Skeleton,
  Stack,
  Table,
  Text,
  TextInput,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useQueryClient } from '@tanstack/react-query'
import { useMyNominations } from '../../hooks/useAlbums'
import { useMyGroups } from '../../hooks/useGroups'
import { useAuth } from '../../hooks/useAuth'
import { albumSearchService } from '../../services/albumSearchService'
import type { UserNominationResponse } from '../../types/album'

export default function MyNominationsPool() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const { data: pool = [], isLoading } = useMyNominations()
  const { data: groups = [] } = useMyGroups(user?.username ?? '')

  const [filter, setFilter] = useState('')
  const [shareTarget, setShareTarget] = useState<UserNominationResponse | null>(null)
  const [selectedGroupIds, setSelectedGroupIds] = useState<string[]>([])
  const [sharing, setSharing] = useState(false)
  const [modalOpened, { open: openModal, close: closeModal }] = useDisclosure(false)

  const filtered = useMemo(() => {
    if (!filter) return pool
    const q = filter.toLowerCase()
    return pool.filter(
      (item) =>
        item.album.title.toLowerCase().includes(q) ||
        item.album.artist.toLowerCase().includes(q),
    )
  }, [pool, filter])

  const openShare = (item: UserNominationResponse) => {
    setShareTarget(item)
    setSelectedGroupIds([])
    openModal()
  }

  const closeShare = () => {
    setShareTarget(null)
    setSelectedGroupIds([])
    closeModal()
  }

  const handleShare = async () => {
    if (!shareTarget || selectedGroupIds.length === 0) return
    setSharing(true)
    const results = await Promise.allSettled(
      selectedGroupIds.map((id) =>
        albumSearchService.nominateToGroup(Number(id), shareTarget.album.id),
      ),
    )
    const failed = results.filter((r) => r.status === 'rejected').length
    const succeeded = results.length - failed

    if (succeeded > 0) {
      qc.invalidateQueries({ queryKey: ['users', 'me', 'nominations'] })
      selectedGroupIds.forEach((id) =>
        qc.invalidateQueries({ queryKey: ['groups', Number(id), 'albums'] }),
      )
      notifications.show({
        color: 'green',
        message: `"${shareTarget.album.title}" shared to ${succeeded} group${succeeded > 1 ? 's' : ''}`,
      })
    }
    if (failed > 0) {
      notifications.show({ color: 'red', message: `${failed} group(s) could not be updated` })
    }
    setSharing(false)
    closeShare()
  }

  const eligibleGroups = useMemo(
    () => (shareTarget ? groups.filter((g) => !shareTarget.nominated_group_ids.includes(g.id)) : []),
    [shareTarget, groups],
  )

  if (isLoading) {
    return (
      <Stack gap="xs">
        {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} h={56} radius="sm" />)}
      </Stack>
    )
  }

  return (
    <>
      <Stack gap="md">
        <TextInput
          placeholder="Filter by album or artist…"
          value={filter}
          onChange={(e) => setFilter(e.currentTarget.value)}
        />

        {filtered.length === 0 ? (
          <Text size="sm" c="dimmed">
            {pool.length === 0
              ? "You haven't nominated any albums yet."
              : 'No nominations match your filter.'}
          </Text>
        ) : (
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th w={52} />
                <Table.Th>Album</Table.Th>
                <Table.Th>Artist</Table.Th>
                <Table.Th w={80}>Groups</Table.Th>
                <Table.Th w={72} />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {filtered.map((item) => (
                <Table.Tr key={item.album.id}>
                  <Table.Td>
                    {item.album.cover_url ? (
                      <Image src={item.album.cover_url} w={36} h={36} radius="sm" />
                    ) : (
                      <div
                        style={{
                          width: 36,
                          height: 36,
                          background: 'var(--mantine-color-dark-5)',
                          borderRadius: 4,
                        }}
                      />
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" fw={500}>{item.album.title}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">{item.album.artist}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge size="sm" variant="light" color="gray">
                      {item.nominated_group_ids.length}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Button
                      size="xs"
                      variant="light"
                      onClick={() => openShare(item)}
                    >
                      Share
                    </Button>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Stack>

      <Modal
        opened={modalOpened}
        onClose={closeShare}
        title={shareTarget ? `Share "${shareTarget.album.title}"` : 'Share to groups'}
        size="sm"
        centered
      >
        <Stack gap="md">
          {eligibleGroups.length === 0 ? (
            <Text size="sm" c="dimmed">
              This album is already nominated in all your groups.
            </Text>
          ) : (
            <>
              <Text size="sm" c="dimmed">Select groups to add this album to:</Text>
              <Checkbox.Group value={selectedGroupIds} onChange={setSelectedGroupIds}>
                <Stack gap="xs">
                  {eligibleGroups.map((g) => (
                    <Checkbox key={g.id} value={String(g.id)} label={g.name} />
                  ))}
                </Stack>
              </Checkbox.Group>
              <Group justify="flex-end" gap="xs">
                <Button variant="subtle" size="sm" onClick={closeShare}>Cancel</Button>
                <Button
                  size="sm"
                  disabled={selectedGroupIds.length === 0}
                  loading={sharing}
                  onClick={handleShare}
                >
                  Share to {selectedGroupIds.length > 0 ? `${selectedGroupIds.length} group${selectedGroupIds.length > 1 ? 's' : ''}` : 'groups'}
                </Button>
              </Group>
            </>
          )}
        </Stack>
      </Modal>
    </>
  )
}
