import { useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  Badge,
  Box,
  Group,
  ScrollArea,
  SegmentedControl,
  Skeleton,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import AppShell from '../components/layout/AppShell'
import TodaysSpin from '../components/spin/TodaysSpin'
import ReviewHistory from '../components/groups/ReviewHistory'
import GroupInfo from '../components/groups/GroupInfo'
import { useGroup, useGroupMembers } from '../hooks/useGroups'
import { useGroupAlbums } from '../hooks/useAlbums'

type Tab = 'spin' | 'history' | 'info'

const ROLE_COLOR = { owner: 'violet', admin: 'blue', member: 'gray' } as const

export default function GroupPage() {
  const { groupId } = useParams<{ groupId: string }>()
  const gid = Number(groupId)
  const [tab, setTab] = useState<Tab>('spin')

  const { data: group, isLoading: groupLoading } = useGroup(gid)
  const { data: members = [], isLoading: membersLoading } = useGroupMembers(gid)
  const { data: reviewedAlbums = [], isLoading: albumsLoading } = useGroupAlbums(gid, 'reviewed')

  return (
    <AppShell>
      <Stack gap="lg">
        {groupLoading ? (
          <Skeleton h={40} w={200} />
        ) : (
          <div>
            <Group gap="sm" mb={4}>
              <Title order={3}>{group?.name}</Title>
              {group?.current_user_role && (
                <Badge size="sm" color={ROLE_COLOR[group.current_user_role]} variant="light">
                  {group.current_user_role}
                </Badge>
              )}
            </Group>
            <Text size="sm" c="dimmed">
              {group?.is_public ? 'Public' : 'Private'} · {group?.member_count} member{group?.member_count !== 1 ? 's' : ''}
            </Text>
          </div>
        )}

        <Box
          p={3}
          style={{
            background: 'linear-gradient(135deg, var(--mantine-color-violet-9) 0%, var(--mantine-color-dark-6) 100%)',
            borderRadius: 'var(--mantine-radius-sm)',
          }}
        >
          <SegmentedControl
            fullWidth
            value={tab}
            onChange={(v) => setTab(v as Tab)}
            data={[
              { label: "Today's Spin", value: 'spin' },
              { label: 'Review History', value: 'history' },
              { label: 'Group Info', value: 'info' },
            ]}
            styles={{ root: { background: 'transparent' } }}
          />
        </Box>

        {tab === 'spin' && (
          <TodaysSpin groupId={gid} group={group} />
        )}

        {tab === 'history' && (
          <ScrollArea>
            <ReviewHistory
              groupId={gid}
              albums={reviewedAlbums}
              members={members}
              isLoading={albumsLoading || membersLoading}
            />
          </ScrollArea>
        )}

        {tab === 'info' && group && (
          <GroupInfo group={group} />
        )}
        {tab === 'info' && groupLoading && (
          <Skeleton h={300} radius="md" />
        )}
      </Stack>
    </AppShell>
  )
}
