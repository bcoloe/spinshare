import { Image, Skeleton, Table, Text } from '@mantine/core'
import { useMyReview } from '../../hooks/useDailySpin'
import type { GroupAlbumResponse } from '../../types/album'
import type { GroupMemberResponse } from '../../types/group'

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

interface RowProps {
  ga: GroupAlbumResponse
  members: GroupMemberResponse[]
}

function ReviewHistoryRow({ ga, members }: RowProps) {
  const { data: review, isLoading } = useMyReview(ga.album_id)
  const { album } = ga

  const nominator = members.find((m) => m.user_id === ga.added_by)?.username ?? '—'

  return (
    <Table.Tr>
      <Table.Td>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
          <Image
            src={album.cover_url ?? undefined}
            w={36}
            h={36}
            radius="sm"
            style={{ flexShrink: 0 }}
            fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='36' height='36'%3E%3Crect width='36' height='36' fill='%23373A40'/%3E%3C/svg%3E"
          />
          <div style={{ minWidth: 0 }}>
            <Text size="sm" fw={500} lineClamp={1}>{album.title}</Text>
            <Text size="xs" c="dimmed" lineClamp={1}>{album.artist}</Text>
          </div>
        </div>
      </Table.Td>
      <Table.Td>
        <Text size="sm" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
          {formatDate(ga.selected_date)}
        </Text>
      </Table.Td>
      <Table.Td>
        {isLoading ? (
          <Skeleton h={16} w={40} />
        ) : review ? (
          <Text size="sm" fw={500}>{review.rating} / 10</Text>
        ) : (
          <Text size="sm" c="dimmed">—</Text>
        )}
      </Table.Td>
      <Table.Td style={{ maxWidth: 240 }}>
        {isLoading ? (
          <Skeleton h={16} w={120} />
        ) : review?.comment ? (
          <Text size="xs" c="dimmed" fs="italic" lineClamp={2}>
            &ldquo;{review.comment}&rdquo;
          </Text>
        ) : (
          <Text size="xs" c="dimmed">—</Text>
        )}
      </Table.Td>
      <Table.Td>
        <Text size="sm" c="dimmed">{nominator}</Text>
      </Table.Td>
    </Table.Tr>
  )
}

interface Props {
  groupId: number
  albums: GroupAlbumResponse[]
  members: GroupMemberResponse[]
  isLoading: boolean
}

export default function ReviewHistory({ albums, members, isLoading }: Props) {
  if (isLoading) {
    return (
      <div>
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} h={52} mb={4} radius="sm" />
        ))}
      </div>
    )
  }

  if (!albums.length) {
    return (
      <Text c="dimmed" size="sm">No albums have been reviewed yet.</Text>
    )
  }

  return (
    <Table highlightOnHover verticalSpacing="sm">
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Album</Table.Th>
          <Table.Th>Date</Table.Th>
          <Table.Th>Rating</Table.Th>
          <Table.Th>Notes</Table.Th>
          <Table.Th>Nominated By</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {albums.map((ga) => (
          <ReviewHistoryRow key={ga.id} ga={ga} members={members} />
        ))}
      </Table.Tbody>
    </Table>
  )
}
