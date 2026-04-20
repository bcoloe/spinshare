import { ActionIcon, Badge, Group, Image, Text } from '@mantine/core'
import { IconTrash } from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import { useRemoveGroupAlbum } from '../../hooks/useAlbums'
import { useAuth } from '../../hooks/useAuth'
import type { GroupAlbumResponse } from '../../types/album'
import type { GroupDetailResponse } from '../../types/group'
import { ApiError } from '../../services/apiClient'

const STATUS_COLOR = {
  pending: 'gray',
  selected: 'blue',
  reviewed: 'green',
} as const

interface Props {
  groupAlbum: GroupAlbumResponse
  group: GroupDetailResponse
}

export default function AlbumRow({ groupAlbum, group }: Props) {
  const { user } = useAuth()
  const remove = useRemoveGroupAlbum(group.id)

  const canRemove =
    groupAlbum.added_by === user?.id ||
    group.current_user_role === 'owner' ||
    group.current_user_role === 'admin'

  const handleRemove = async () => {
    try {
      await remove.mutateAsync(groupAlbum.id)
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not remove nomination'
      notifications.show({ color: 'red', message })
    }
  }

  const { album } = groupAlbum

  return (
    <Group justify="space-between" wrap="nowrap">
      <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
        <Image
          src={album.cover_url ?? undefined}
          w={44}
          h={44}
          radius="sm"
          fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='44' height='44'%3E%3Crect width='44' height='44' fill='%23373A40'/%3E%3C/svg%3E"
        />
        <div style={{ minWidth: 0 }}>
          <Text size="sm" fw={500} lineClamp={1}>{album.title}</Text>
          <Text size="xs" c="dimmed" lineClamp={1}>{album.artist}</Text>
        </div>
      </Group>
      <Group gap="sm" style={{ flexShrink: 0 }}>
        <Badge size="xs" color={STATUS_COLOR[groupAlbum.status]} variant="light">
          {groupAlbum.status}
        </Badge>
        {canRemove && (
          <ActionIcon
            size="sm"
            variant="subtle"
            color="red"
            onClick={handleRemove}
            loading={remove.isPending}
          >
            <IconTrash size={14} />
          </ActionIcon>
        )}
      </Group>
    </Group>
  )
}
