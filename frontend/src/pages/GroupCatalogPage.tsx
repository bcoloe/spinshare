import { useParams } from 'react-router-dom'
import { Button, Divider, Skeleton, Stack, Tabs, Text, Title } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { IconPlus } from '@tabler/icons-react'
import AppShell from '../components/layout/AppShell'
import AlbumRow from '../components/albums/AlbumRow'
import AlbumSearchModal from '../components/albums/AlbumSearchModal'
import { useGroupAlbums } from '../hooks/useAlbums'
import { useGroup } from '../hooks/useGroups'

const STATUSES = [
  { value: 'all', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'selected', label: 'Selected' },
  { value: 'reviewed', label: 'Reviewed' },
] as const

export default function GroupCatalogPage() {
  const { groupId } = useParams<{ groupId: string }>()
  const gid = Number(groupId)
  const { data: group } = useGroup(gid)
  const [searchOpened, { open, close }] = useDisclosure()

  return (
    <AppShell>
      <Stack gap="lg" maw={640}>
        <Stack gap="xs">
          <Title order={3}>{group?.name} — Catalog</Title>
          <Button
            leftSection={<IconPlus size={16} />}
            size="sm"
            style={{ alignSelf: 'flex-start' }}
            onClick={open}
          >
            Nominate album
          </Button>
        </Stack>

        <Tabs defaultValue="all">
          <Tabs.List>
            {STATUSES.map(({ value, label }) => (
              <Tabs.Tab key={value} value={value}>{label}</Tabs.Tab>
            ))}
          </Tabs.List>

          {STATUSES.map(({ value }) => (
            <Tabs.Panel key={value} value={value} pt="md">
              <CatalogList groupId={gid} status={value === 'all' ? undefined : value} group={group} />
            </Tabs.Panel>
          ))}
        </Tabs>
      </Stack>

      {group && (
        <AlbumSearchModal groupId={gid} opened={searchOpened} onClose={close} />
      )}
    </AppShell>
  )
}

function CatalogList({
  groupId,
  status,
  group,
}: {
  groupId: number
  status?: string
  group: ReturnType<typeof useGroup>['data']
}) {
  const { data: albums, isLoading } = useGroupAlbums(groupId, status)

  if (isLoading) {
    return (
      <Stack gap="xs">
        {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} h={56} radius="sm" />)}
      </Stack>
    )
  }

  if (!albums?.length) {
    return <Text c="dimmed" size="sm">No albums here yet.</Text>
  }

  return (
    <Stack gap="xs">
      {albums.map((ga, i) => (
        <div key={ga.id}>
          {group && <AlbumRow groupAlbum={ga} group={group} />}
          {i < albums.length - 1 && <Divider my="xs" />}
        </div>
      ))}
    </Stack>
  )
}
