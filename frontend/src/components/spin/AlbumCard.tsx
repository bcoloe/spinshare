import { Anchor, Badge, Group, Image, Overlay, Stack, Text, Title } from '@mantine/core'
import { Link } from 'react-router-dom'
import { useAlbumNominationCounts } from '../../hooks/useAlbums'
import type { AlbumResponse } from '../../types/album'
import NominationBadge from '../albums/NominationBadge'

interface Props {
  album: AlbumResponse
  // The group whose spin this card is shown in. When provided together with
  // showGroupCount, a "N in this group" nomination count is displayed.
  groupId?: number
  // Whether to request/show the group-scoped nomination count. False for the
  // global and bot groups, which have no meaningful member nomination count.
  showGroupCount?: boolean
  // Mask the group figure as "??" (chaos-mode groups). Only relevant when
  // showGroupCount is true.
  maskGroupCount?: boolean
}

export default function AlbumCard({ album, groupId, showGroupCount = false, maskGroupCount = false }: Props) {
  const year = album.release_date ? album.release_date.slice(0, 4) : null
  const { data: counts } = useAlbumNominationCounts(
    album.id,
    showGroupCount ? groupId : undefined,
  )

  const total = counts?.total_count
  const groupCount = showGroupCount ? counts?.group_count ?? null : null
  const maskGroup = showGroupCount && maskGroupCount

  return (
    <Group gap="lg" align="flex-start">
      <div style={{ position: 'relative', flexShrink: 0 }}>
        <Image
          src={album.cover_url ?? undefined}
          alt={`${album.title} cover`}
          w={180}
          h={180}
          radius="md"
          fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180'%3E%3Crect width='180' height='180' fill='%23373A40'/%3E%3C/svg%3E"
        />
        {!album.cover_url && (
          <Overlay color="#000" backgroundOpacity={0.1} radius="md" />
        )}
      </div>

      <Stack gap="xs" style={{ flex: 1, minWidth: 0 }}>
        <div>
          <Anchor component={Link} to={`/albums/${album.id}`} underline="hover" c="inherit">
            <Title order={3} lineClamp={2}>{album.title}</Title>
          </Anchor>
          <Text size="lg" c="dimmed">{album.artist}</Text>
          {year && <Text size="sm" c="dimmed">{year}</Text>}
        </div>
        {album.genres.length > 0 && (
          <Group gap="xs" wrap="wrap">
            {album.genres.slice(0, 4).map((g) => (
              <Badge key={g} size="xs" variant="light" color="violet">
                {g}
              </Badge>
            ))}
          </Group>
        )}
        {total !== undefined && (
          <Group gap="xs">
            <NominationBadge total={total} groupCount={groupCount} maskGroup={maskGroup} />
          </Group>
        )}
      </Stack>
    </Group>
  )
}
