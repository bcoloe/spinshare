import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  ActionIcon,
  Affix,
  Badge,
  Box,
  Button,
  Group,
  Paper,
  ScrollArea,
  SegmentedControl,
  Skeleton,
  Stack,
  Text,
  ThemeIcon,
  Title,
  Tooltip,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useDisclosure, useMediaQuery } from '@mantine/hooks'
import { IconDoorExit, IconLock, IconPlus, IconSettings, IconStar, IconStarFilled, IconUserPlus, IconUsersGroup } from '@tabler/icons-react'
import AppShell from '../components/layout/AppShell'
import TodaysSpin from '../components/spin/TodaysSpin'
import ReviewHistory from '../components/groups/ReviewHistory'
import GroupInfo from '../components/groups/GroupInfo'
import LeaveGroupModal from '../components/groups/LeaveGroupModal'
import InviteUserModal from '../components/groups/InviteUserModal'
import MyNominations from '../components/groups/MyNominations'
import AlbumSearchModal from '../components/albums/AlbumSearchModal'
import { useGroup, useGroupMembers, useJoinGroup } from '../hooks/useGroups'
import { useGroupHistory, useNominationCount } from '../hooks/useAlbums'
import { useFavoriteGroup } from '../context/FavoriteGroupContext'
import { useAuth } from '../hooks/useAuth'
import { ApiError } from '../services/apiClient'

type Tab = 'spin' | 'history' | 'info' | 'nominations'

const ROLE_COLOR = { owner: 'violet', admin: 'blue', member: 'gray' } as const

export default function GroupPage() {
  const { groupId } = useParams<{ groupId: string }>()
  const gid = Number(groupId)
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab: Tab = (searchParams.get('tab') as Tab) ?? 'spin'
  const focusAlbumId = searchParams.get('album') ? Number(searchParams.get('album')) : null
  const [leaveOpened, { open: openLeave, close: closeLeave }] = useDisclosure(false)
  const [inviteOpened, { open: openInvite, close: closeInvite }] = useDisclosure(false)
  const [nominateOpened, { open: openNominate, close: closeNominate }] = useDisclosure(false)
  const isMobile = useMediaQuery('(max-width: 768px)')

  const { data: group, isLoading: groupLoading } = useGroup(gid)
  const isMember = !!group?.current_user_role
  const { data: members = [], isLoading: membersLoading } = useGroupMembers(gid, isMember)
  const { data: historyAlbums = [], isLoading: albumsLoading } = useGroupHistory(gid, isMember)
  const { data: nominationCount } = useNominationCount(gid, isMember)
  const joinGroup = useJoinGroup()

  const { favoriteId, toggleFavorite } = useFavoriteGroup()
  const { user } = useAuth()

  const handleJoin = async () => {
    if (!group) return
    try {
      await joinGroup.mutateAsync(gid)
      notifications.show({ color: 'green', message: `Joined "${group.name}"` })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not join group'
      notifications.show({ color: 'red', message })
    }
  }

  const canManage =
    group?.current_user_role === 'owner' ||
    group?.current_user_role === 'admin' ||
    // Site admins can access the global group's settings page to toggle dealer
    // mode — its own owner/admin roles don't apply since it has no privileged tier
    (!!group?.is_global && !!user?.is_admin)

  const ROLE_RANK: Record<string, number> = { owner: 0, admin: 1, member: 2 }
  const minRoleToInvite = group?.settings?.min_role_to_add_members ?? 'admin'
  const canInvite =
    !!group?.current_user_role &&
    (ROLE_RANK[group.current_user_role] ?? 99) <= (ROLE_RANK[minRoleToInvite] ?? 99)

  const minRoleToNominate = group?.settings?.min_role_to_nominate ?? 'member'
  const dailyLimit = group?.settings?.daily_nomination_limit ?? null
  const todayCount = nominationCount?.today_count ?? 0
  const dailyLimitReached = dailyLimit !== null && todayCount >= dailyLimit
  const canNominate =
    !!group?.current_user_role &&
    !group?.is_global &&
    (ROLE_RANK[group.current_user_role] ?? 99) <= (ROLE_RANK[minRoleToNominate] ?? 99) &&
    !dailyLimitReached

  const nominateTooltip = group?.is_global
    ? 'Nominations are not open for the global group'
    : dailyLimitReached
      ? `Daily nomination limit of ${dailyLimit} reached — come back tomorrow`
      : "You don't have permission to nominate albums in this group"

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
              {isMember ? (
                <>
                  <Tooltip label={favoriteId === gid ? 'Remove from favorites' : 'Set as favorite group'}>
                    <ActionIcon
                      variant="subtle"
                      color={favoriteId === gid ? 'yellow' : 'gray'}
                      onClick={() => toggleFavorite(gid)}
                      aria-label={favoriteId === gid ? 'Remove from favorites' : 'Set as favorite group'}
                    >
                      {favoriteId === gid ? <IconStarFilled size={18} /> : <IconStar size={18} />}
                    </ActionIcon>
                  </Tooltip>
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
                </>
              ) : group?.is_public ? (
                <Button
                  size="xs"
                  leftSection={<IconUserPlus size={16} />}
                  loading={joinGroup.isPending}
                  onClick={handleJoin}
                >
                  Join group
                </Button>
              ) : null}
            </Group>
          </Group>
        )}

        {!groupLoading && group && !isMember ? (
          <Paper withBorder p="xl" radius="md">
            <Stack align="center" gap="md">
              <ThemeIcon size={48} radius="xl" variant="light" color="violet">
                {group.is_public ? <IconUsersGroup size={26} /> : <IconLock size={26} />}
              </ThemeIcon>
              <Stack align="center" gap={4}>
                <Text fw={600}>You're not a member of this group yet</Text>
                <Text size="sm" c="dimmed" ta="center">
                  {group.is_public
                    ? 'Join to see the daily spin, review history, and nominate albums.'
                    : 'This group is private — ask a member for an invitation to get in.'}
                </Text>
              </Stack>
              {group.is_public && (
                <Button
                  leftSection={<IconUserPlus size={16} />}
                  loading={joinGroup.isPending}
                  onClick={handleJoin}
                >
                  Join group
                </Button>
              )}
            </Stack>
          </Paper>
        ) : (
          <>
            <Box
              p={3}
              style={{
                background:
                  'linear-gradient(135deg, var(--mantine-color-violet-9) 0%, var(--mantine-color-dark-6) 100%)',
                borderRadius: 'var(--mantine-radius-sm)',
              }}
            >
              <ScrollArea type="scroll" scrollbarSize={0}>
                <SegmentedControl
                  fullWidth={!isMobile}
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
              </ScrollArea>
            </Box>

            {tab === 'spin' && <TodaysSpin groupId={gid} group={group} />}

            {tab === 'history' && (
              <ScrollArea>
                <ReviewHistory
                  groupId={gid}
                  albums={historyAlbums}
                  members={members}
                  isLoading={albumsLoading || membersLoading}
                  allowGuessing={group?.settings?.allow_guessing ?? true}
                  focusAlbumId={focusAlbumId}
                />
              </ScrollArea>
            )}

            {tab === 'info' && group && <GroupInfo group={group} />}
            {tab === 'info' && groupLoading && <Skeleton h={300} radius="md" />}

            {tab === 'nominations' && <MyNominations groupId={gid} />}
          </>
        )}
      </Stack>

      {group && isMember && (
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

      {isMember && (
        <>
          <Tooltip label={canNominate ? 'Nominate an album' : nominateTooltip} position="left">
            <Affix position={{ bottom: 24, right: 24 }}>
              <ActionIcon
                size="xl"
                radius="xl"
                variant={canNominate ? 'filled' : 'light'}
                color="violet"
                onClick={canNominate ? openNominate : undefined}
                aria-label="Nominate album"
                style={canNominate ? undefined : { cursor: 'not-allowed', opacity: 0.5 }}
              >
                <IconPlus size={22} />
              </ActionIcon>
            </Affix>
          </Tooltip>

          <AlbumSearchModal groupId={gid} opened={nominateOpened} onClose={closeNominate} />
        </>
      )}
    </AppShell>
  )
}
