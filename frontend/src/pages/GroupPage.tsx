import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  ActionIcon,
  Badge,
  Box,
  Group,
  ScrollArea,
  SegmentedControl,
  Skeleton,
  Stack,
  Text,
  Title,
  Tooltip,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { IconDoorExit, IconSettings, IconUserPlus } from '@tabler/icons-react'
import AppShell from '../components/layout/AppShell'
import TodaysSpin from '../components/spin/TodaysSpin'
import ReviewHistory from '../components/groups/ReviewHistory'
import GroupInfo from '../components/groups/GroupInfo'
import LeaveGroupModal from '../components/groups/LeaveGroupModal'
import InviteUserModal from '../components/groups/InviteUserModal'
import MyNominations from '../components/groups/MyNominations'
import { useGroup, useGroupMembers } from '../hooks/useGroups'
import { useGroupAlbums } from '../hooks/useAlbums'

type Tab = 'spin' | 'history' | 'info' | 'nominations'

const ROLE_COLOR = { owner: 'violet', admin: 'blue', member: 'gray' } as const

export default function GroupPage() {
  const { groupId } = useParams<{ groupId: string }>()
  const gid = Number(groupId)
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab: Tab = (searchParams.get('tab') as Tab) ?? 'spin'
  const [leaveOpened, { open: openLeave, close: closeLeave }] = useDisclosure(false)
  const [inviteOpened, { open: openInvite, close: closeInvite }] = useDisclosure(false)

  const { data: group, isLoading: groupLoading } = useGroup(gid)
  const { data: members = [], isLoading: membersLoading } = useGroupMembers(gid)
  const { data: allAlbums = [], isLoading: albumsLoading } = useGroupAlbums(gid)
  const reviewedAlbums = allAlbums.filter((ga) => ga.selected_date !== null)

  const canManage =
    group?.current_user_role === 'owner' || group?.current_user_role === 'admin'

  const ROLE_RANK: Record<string, number> = { owner: 0, admin: 1, member: 2 }
  const minRoleToInvite = group?.settings?.min_role_to_add_members ?? 'admin'
  const canInvite =
    !!group?.current_user_role &&
    (ROLE_RANK[group.current_user_role] ?? 99) <= (ROLE_RANK[minRoleToInvite] ?? 99)

  return (
    <AppShell>
      <Stack gap="lg">
        {groupLoading ? (
          <Skeleton h={40} w={200} />
        ) : (
          <Group justify="space-between" align="flex-start">
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
                {group?.is_public ? 'Public' : 'Private'} · {group?.member_count} member
                {group?.member_count !== 1 ? 's' : ''}
              </Text>
            </div>

            <Group gap="xs">
              {canInvite && (
                <Tooltip label="Invite member">
                  <ActionIcon variant="subtle" onClick={openInvite}>
                    <IconUserPlus size={18} />
                  </ActionIcon>
                </Tooltip>
              )}
              {canManage && (
                <Tooltip label="Group settings">
                  <ActionIcon
                    variant="subtle"
                    onClick={() => navigate(`/groups/${gid}/settings`)}
                  >
                    <IconSettings size={18} />
                  </ActionIcon>
                </Tooltip>
              )}
              <Tooltip label="Leave group">
                <ActionIcon variant="subtle" color="red" onClick={openLeave}>
                  <IconDoorExit size={18} />
                </ActionIcon>
              </Tooltip>
            </Group>
          </Group>
        )}

        <Box
          p={3}
          style={{
            background:
              'linear-gradient(135deg, var(--mantine-color-violet-9) 0%, var(--mantine-color-dark-6) 100%)',
            borderRadius: 'var(--mantine-radius-sm)',
          }}
        >
          <SegmentedControl
            fullWidth
            value={tab}
            onChange={(v) => setSearchParams({ tab: v })}
            data={[
              { label: "Today's Spin", value: 'spin' },
              { label: 'Review History', value: 'history' },
              { label: 'My Nominations', value: 'nominations' },
              { label: 'Group Info', value: 'info' },
            ]}
            styles={{ root: { background: 'transparent' } }}
          />
        </Box>

        {tab === 'spin' && <TodaysSpin groupId={gid} group={group} />}

        {tab === 'history' && (
          <ScrollArea>
            <ReviewHistory
              groupId={gid}
              albums={reviewedAlbums}
              members={members}
              isLoading={albumsLoading || membersLoading}
              allowGuessing={group?.settings?.allow_guessing ?? true}
            />
          </ScrollArea>
        )}

        {tab === 'info' && group && <GroupInfo group={group} />}
        {tab === 'info' && groupLoading && <Skeleton h={300} radius="md" />}

        {tab === 'nominations' && <MyNominations groupId={gid} />}
      </Stack>

      {group && (
        <>
          <LeaveGroupModal
            groupId={gid}
            groupName={group.name}
            isLastMember={members.length === 1}
            opened={leaveOpened}
            onClose={closeLeave}
          />
          {canInvite && (
            <InviteUserModal groupId={gid} opened={inviteOpened} onClose={closeInvite} />
          )}
        </>
      )}
    </AppShell>
  )
}
