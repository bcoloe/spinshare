import { useMemo, useState } from 'react'
import {
  ActionIcon,
  Badge,
  Button,
  Group,
  Image,
  Skeleton,
  Stack,
  Table,
  Text,
  TextInput,
  UnstyledButton,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import {
  IconChevronDown,
  IconChevronUp,
  IconPlus,
  IconSelector,
  IconTrash,
} from '@tabler/icons-react'
import AlbumSearchModal from '../albums/AlbumSearchModal'
import { notifications } from '@mantine/notifications'
import { useGroupAlbums, useRemoveGroupAlbum } from '../../hooks/useAlbums'
import { useAuth } from '../../hooks/useAuth'
import { ApiError } from '../../services/apiClient'
import type { GroupAlbumResponse } from '../../types/album'

type SortField = 'title' | 'artist' | 'year' | 'status'
type SortDir = 'asc' | 'desc'

const STATUS_COLOR = {
  pending: 'blue',
  selected: 'violet',
  reviewed: 'green',
} as const

function getYear(releaseDate: string | null): string {
  return releaseDate ? releaseDate.slice(0, 4) : '—'
}

function getValue(ga: GroupAlbumResponse, field: SortField): string {
  switch (field) {
    case 'title': return ga.album.title
    case 'artist': return ga.album.artist
    case 'year': return ga.album.release_date ?? ''
    case 'status': return ga.status
  }
}

interface SortButtonProps {
  field: SortField
  label: string
  active: SortField
  dir: SortDir
  onClick: (f: SortField) => void
}

function SortButton({ field, label, active, dir, onClick }: SortButtonProps) {
  const Icon =
    active !== field ? IconSelector : dir === 'asc' ? IconChevronUp : IconChevronDown
  return (
    <UnstyledButton
      onClick={() => onClick(field)}
      style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}
      c="dimmed"
    >
      {label}
      <Icon size={13} />
    </UnstyledButton>
  )
}

interface Props {
  groupId: number
}

export default function MyNominations({ groupId }: Props) {
  const { user } = useAuth()
  const { data: allAlbums = [], isLoading } = useGroupAlbums(groupId)
  const removeGroupAlbum = useRemoveGroupAlbum(groupId)
  const [filter, setFilter] = useState('')
  const [sortField, setSortField] = useState<SortField>('title')
  const [sortDir, setSortDir] = useState<SortDir>('asc')
  const [nominateOpened, { open: openNominate, close: closeNominate }] = useDisclosure(false)

  const myNominations = useMemo(
    () => allAlbums.filter((ga) => ga.added_by === user?.id),
    [allAlbums, user],
  )

  const filtered = useMemo(() => {
    const q = filter.toLowerCase()
    if (!q) return myNominations
    return myNominations.filter(
      (ga) =>
        ga.album.title.toLowerCase().includes(q) ||
        ga.album.artist.toLowerCase().includes(q),
    )
  }, [myNominations, filter])

  const sorted = useMemo(
    () =>
      [...filtered].sort((a, b) => {
        const av = getValue(a, sortField)
        const bv = getValue(b, sortField)
        return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
      }),
    [filtered, sortField, sortDir],
  )

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDir('asc')
    }
  }

  const handleDelete = async (ga: GroupAlbumResponse) => {
    try {
      await removeGroupAlbum.mutateAsync(ga.id)
      notifications.show({ color: 'green', message: 'Nomination removed' })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not remove nomination'
      notifications.show({ color: 'red', message })
    }
  }

  if (isLoading) {
    return (
      <Stack gap="xs">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} h={56} radius="sm" />
        ))}
      </Stack>
    )
  }

  return (
    <>
    <Stack gap="md">
      <Group justify="space-between">
        <TextInput
          placeholder="Filter by album or artist..."
          value={filter}
          onChange={(e) => setFilter(e.currentTarget.value)}
          style={{ flex: 1 }}
        />
        <Button leftSection={<IconPlus size={16} />} onClick={openNominate}>
          Nominate
        </Button>
      </Group>

      {sorted.length === 0 ? (
        <Text c="dimmed" size="sm">
          {myNominations.length === 0
            ? "You haven't nominated any albums yet."
            : 'No nominations match your filter.'}
        </Text>
      ) : (
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th w={52} />
              <Table.Th>
                <SortButton field="title" label="Album" active={sortField} dir={sortDir} onClick={handleSort} />
              </Table.Th>
              <Table.Th>
                <SortButton field="artist" label="Artist" active={sortField} dir={sortDir} onClick={handleSort} />
              </Table.Th>
              <Table.Th w={72}>
                <SortButton field="year" label="Year" active={sortField} dir={sortDir} onClick={handleSort} />
              </Table.Th>
              <Table.Th w={110}>
                <SortButton field="status" label="Status" active={sortField} dir={sortDir} onClick={handleSort} />
              </Table.Th>
              <Table.Th w={40} />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {sorted.map((ga) => (
              <Table.Tr key={ga.id}>
                <Table.Td>
                  {ga.album.cover_url ? (
                    <Image src={ga.album.cover_url} w={36} h={36} radius="sm" />
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
                  <Text size="sm" fw={500}>{ga.album.title}</Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">{ga.album.artist}</Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">{getYear(ga.album.release_date)}</Text>
                </Table.Td>
                <Table.Td>
                  <Badge size="sm" color={STATUS_COLOR[ga.status]} variant="light">
                    {ga.status}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  {ga.status === 'pending' && (
                    <ActionIcon
                      size="sm"
                      variant="subtle"
                      color="red"
                      onClick={() => handleDelete(ga)}
                      loading={removeGroupAlbum.isPending}
                    >
                      <IconTrash size={14} />
                    </ActionIcon>
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
    <AlbumSearchModal groupId={groupId} opened={nominateOpened} onClose={closeNominate} />
    </>
  )
}
