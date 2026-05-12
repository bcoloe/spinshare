import { Fragment } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import {
  ActionIcon,
  Anchor,
  AppShell as MantineAppShell,
  Avatar,
  Burger,
  Button,
  Divider,
  Group,
  Indicator,
  Menu,
  NavLink,
  Popover,
  ScrollArea,
  Skeleton,
  Stack,
  Text,
  TextInput,
  Title,
  UnstyledButton,
} from '@mantine/core'
import { useState } from 'react'
import { useDisclosure } from '@mantine/hooks'
import {
  IconBell,
  IconCheck,
  IconDisc,
  IconLayoutSidebarLeftCollapse,
  IconLayoutSidebarLeftExpand,
  IconLogout,
  IconPlus,
  IconSearch,
  IconStar,
  IconStarFilled,
  IconUser,
  IconX,
} from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import { useEffect } from 'react'
import { useAuth } from '../../hooks/useAuth'
import { useMyGroups, useMyPendingInvitations, useAcceptInvitation, useDeclineInvitation } from '../../hooks/useGroups'
import { useFavoriteGroup } from '../../context/FavoriteGroupContext'
import { useUnreadNotifications, useMarkAllNotificationsRead, useNotificationHistory } from '../../hooks/useNotifications'
import { usePlayer } from '../../context/PlayerContext'
import { ApiError } from '../../services/apiClient'
import CreateGroupModal from '../groups/CreateGroupModal'
import SearchModal from '../search/SearchModal'
import PlayerBar from './PlayerBar'

interface AppShellProps {
  children: React.ReactNode
}

export default function AppShell({ children }: AppShellProps) {
  const { user, logout } = useAuth()
  const { status: playerStatus, playingAlbumMeta, minimized } = usePlayer()
  const showFooter = playingAlbumMeta !== null && (playerStatus === 'ready' || playerStatus === 'playing' || playerStatus === 'paused')
  const footerHeight = minimized ? 48 : 220
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileOpened, { toggle: toggleMobile }] = useDisclosure()
  const [desktopOpened, { toggle: toggleDesktop }] = useDisclosure(true)
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure()
  const [searchOpened, { open: openSearch, close: closeSearch }] = useDisclosure()

  const { data: groups, isLoading } = useMyGroups(user?.username ?? '')
  const { favoriteId, toggleFavorite, clearIfStale } = useFavoriteGroup()
  const [sidebarFilter, setSidebarFilter] = useState('')
  const { data: pendingInvitations = [] } = useMyPendingInvitations()
  const { data: unreadNotifications = [] } = useUnreadNotifications()
  const acceptInvitation = useAcceptInvitation()
  const declineInvitation = useDeclineInvitation()
  const markAllRead = useMarkAllNotificationsRead()
  const [bellOpened, { toggle: toggleBell, close: closeBell }] = useDisclosure()
  const [showHistory, setShowHistory] = useState(false)
  const { data: historyNotifications, isLoading: historyLoading } = useNotificationHistory(showHistory && bellOpened)

  const totalUnread = pendingInvitations.length + unreadNotifications.length

  // Snapshot notifications when the bell opens so the list stays visible
  // while markAllRead fires and the query refetches to empty in the background.
  const [notificationSnapshot, setNotificationSnapshot] = useState(unreadNotifications)

  useEffect(() => {
    if (bellOpened) {
      setNotificationSnapshot(unreadNotifications)
      if (unreadNotifications.length > 0) markAllRead.mutate()
    } else {
      setShowHistory(false)
    }
  }, [bellOpened]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (groups) clearIfStale(groups.map((g) => g.id))
  }, [groups, clearIfStale])

  const handleAccept = async (token: string, groupName: string, groupId: number) => {
    try {
      await acceptInvitation.mutateAsync(token)
      closeBell()
      notifications.show({ color: 'green', message: `Joined ${groupName}!` })
      navigate(`/groups/${groupId}`)
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not accept invitation'
      notifications.show({ color: 'red', message })
    }
  }

  const handleDecline = async (token: string) => {
    try {
      await declineInvitation.mutateAsync(token)
    } catch {
      notifications.show({ color: 'red', message: 'Could not decline invitation' })
    }
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <MantineAppShell
      header={{ height: 56 }}
      navbar={{
        width: 220,
        breakpoint: 'sm',
        collapsed: { mobile: !mobileOpened, desktop: !desktopOpened },
      }}
      footer={showFooter ? { height: footerHeight } : undefined}
      padding="md"
    >
      <MantineAppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group gap="sm">
            <Burger opened={mobileOpened} onClick={toggleMobile} hiddenFrom="sm" size="sm" />
            <ActionIcon
              variant="subtle"
              visibleFrom="sm"
              onClick={toggleDesktop}
              aria-label="Toggle sidebar"
            >
              {desktopOpened
                ? <IconLayoutSidebarLeftCollapse size={20} />
                : <IconLayoutSidebarLeftExpand size={20} />}
            </ActionIcon>
            <IconDisc size={22} />
            <Title order={4}>SpinShare</Title>
          </Group>

          <Group gap="xs">
            <Popover
              opened={bellOpened}
              onClose={closeBell}
              position="bottom-end"
              shadow="md"
              width={300}
            >
              <Popover.Target>
                <Indicator
                  disabled={totalUnread === 0}
                  label={totalUnread}
                  size={16}
                  color="violet"
                >
                  <ActionIcon variant="subtle" onClick={toggleBell} aria-label="Notifications">
                    <IconBell size={18} />
                  </ActionIcon>
                </Indicator>
              </Popover.Target>
              <Popover.Dropdown p="sm">
                <Stack gap="md">
                  {pendingInvitations.length === 0 && notificationSnapshot.length === 0 && (
                    <Text size="sm" c="dimmed">No new notifications</Text>
                  )}

                  {pendingInvitations.length > 0 && (
                    <div>
                      <Text size="xs" fw={600} c="dimmed" tt="uppercase" mb="xs">
                        Invitations
                      </Text>
                      <Stack gap="xs">
                        {pendingInvitations.map((inv) => (
                          <Group key={inv.id} justify="space-between" wrap="nowrap">
                            <div>
                              <Text size="sm" fw={500} lineClamp={1}>{inv.group_name}</Text>
                              <Text size="xs" c="dimmed">from {inv.inviter_username}</Text>
                            </div>
                            <Group gap={4} wrap="nowrap">
                              <ActionIcon
                                size="sm"
                                variant="light"
                                color="green"
                                loading={acceptInvitation.isPending}
                                onClick={() => handleAccept(inv.token, inv.group_name, inv.group_id)}
                                aria-label="Accept"
                              >
                                <IconCheck size={14} />
                              </ActionIcon>
                              <ActionIcon
                                size="sm"
                                variant="light"
                                color="red"
                                loading={declineInvitation.isPending}
                                onClick={() => handleDecline(inv.token)}
                                aria-label="Decline"
                              >
                                <IconX size={14} />
                              </ActionIcon>
                            </Group>
                          </Group>
                        ))}
                      </Stack>
                    </div>
                  )}

                  {notificationSnapshot.length > 0 && (
                    <div>
                      <Text size="xs" fw={600} c="dimmed" tt="uppercase" mb="xs">
                        New Activity
                      </Text>
                      <Stack gap={0}>
                        {notificationSnapshot.map((n, i) => (
                          <Fragment key={n.id}>
                            {i > 0 && <Divider />}
                            <Text
                              size="sm"
                              py={6}
                              style={{ cursor: n.group_id ? 'pointer' : 'default' }}
                              onClick={() => {
                                if (n.group_id) {
                                  closeBell()
                                  const dest = n.type === 'member_reviewed_album'
                                    ? `/groups/${n.group_id}?tab=history`
                                    : `/groups/${n.group_id}`
                                  navigate(dest)
                                }
                              }}
                            >
                              {n.message}
                            </Text>
                          </Fragment>
                        ))}
                      </Stack>
                    </div>
                  )}

                  <div>
                    <Anchor
                      component="button"
                      size="xs"
                      c="dimmed"
                      onClick={() => setShowHistory((v) => !v)}
                    >
                      {showHistory ? 'Hide history' : 'View older notifications'}
                    </Anchor>
                    {showHistory && (
                      <div style={{ marginTop: 8 }}>
                        <Text size="xs" fw={600} c="dimmed" tt="uppercase" mb="xs">
                          History
                        </Text>
                        <ScrollArea h={200}>
                          {historyLoading ? (
                            <Stack gap="xs">
                              {Array.from({ length: 3 }).map((_, i) => (
                                <Skeleton key={i} h={18} radius="sm" />
                              ))}
                            </Stack>
                          ) : !historyNotifications?.length ? (
                            <Text size="xs" c="dimmed">No notification history</Text>
                          ) : (
                            <Stack gap={0}>
                              {historyNotifications.map((n, i) => (
                                <Fragment key={n.id}>
                                  {i > 0 && <Divider />}
                                  <Text
                                    size="sm"
                                    py={6}
                                    c={n.read_at ? 'dimmed' : undefined}
                                    style={{ cursor: n.group_id ? 'pointer' : 'default' }}
                                    onClick={() => {
                                      if (n.group_id) {
                                        closeBell()
                                        const dest = n.type === 'member_reviewed_album'
                                          ? `/groups/${n.group_id}?tab=history`
                                          : `/groups/${n.group_id}`
                                        navigate(dest)
                                      }
                                    }}
                                  >
                                    {n.message}
                                  </Text>
                                </Fragment>
                              ))}
                            </Stack>
                          )}
                        </ScrollArea>
                      </div>
                    )}
                  </div>
                </Stack>
              </Popover.Dropdown>
            </Popover>

          <Menu shadow="md" width={180}>
            <Menu.Target>
              <UnstyledButton>
                <Avatar size="sm" radius="xl" color="violet">
                  {user?.username?.[0]?.toUpperCase()}
                </Avatar>
              </UnstyledButton>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Label>{user?.username}</Menu.Label>
              <Menu.Item leftSection={<IconUser size={14} />} onClick={() => navigate('/profile')}>
                Profile
              </Menu.Item>
              <Menu.Divider />
              <Menu.Item color="red" leftSection={<IconLogout size={14} />} onClick={handleLogout}>
                Sign out
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
          </Group>
        </Group>
      </MantineAppShell.Header>

      <MantineAppShell.Navbar p="md">
        <MantineAppShell.Section>
          <NavLink
            label="Dashboard"
            component={Link}
            to="/"
            active={location.pathname === '/'}
          />
          <Button
            fullWidth
            variant="subtle"
            justify="start"
            leftSection={<IconSearch size={16} />}
            mt={4}
            onClick={openSearch}
          >
            Search
          </Button>
        </MantineAppShell.Section>

        <MantineAppShell.Section grow component={ScrollArea} mt="md">
          <Text size="xs" fw={600} c="dimmed" mb="xs" tt="uppercase">
            Your Groups
          </Text>
          {!isLoading && (groups?.length ?? 0) > 0 && (
            <TextInput
              size="xs"
              placeholder="Filter..."
              leftSection={<IconSearch size={12} />}
              value={sidebarFilter}
              onChange={(e) => setSidebarFilter(e.currentTarget.value)}
              mb="xs"
            />
          )}
          {isLoading
            ? Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} h={32} mb={4} radius="sm" />)
            : [...(groups ?? [])]
                .sort((a, b) => a.name.localeCompare(b.name))
                .filter((g) => !sidebarFilter || g.name.toLowerCase().includes(sidebarFilter.toLowerCase()))
                .map((g) => (
                  <NavLink
                    key={g.id}
                    label={g.name}
                    component={Link}
                    to={`/groups/${g.id}`}
                    active={location.pathname.startsWith(`/groups/${g.id}`)}
                    rightSection={
                      <ActionIcon
                        size="xs"
                        variant="subtle"
                        color={favoriteId === g.id ? 'yellow' : 'gray'}
                        onClick={(e) => { e.preventDefault(); e.stopPropagation(); toggleFavorite(g.id) }}
                        aria-label={favoriteId === g.id ? 'Unset default group' : 'Set as default group'}
                      >
                        {favoriteId === g.id ? <IconStarFilled size={12} /> : <IconStar size={12} />}
                      </ActionIcon>
                    }
                  />
                ))}
          {!isLoading && groups?.length === 0 && (
            <Text size="xs" c="dimmed">No groups yet</Text>
          )}
        </MantineAppShell.Section>

        <MantineAppShell.Section>
          <Button
            fullWidth
            variant="light"
            leftSection={<IconPlus size={16} />}
            onClick={openCreate}
          >
            New group
          </Button>
        </MantineAppShell.Section>
      </MantineAppShell.Navbar>

      <MantineAppShell.Main>{children}</MantineAppShell.Main>

      {showFooter && (
        <MantineAppShell.Footer>
          <PlayerBar />
        </MantineAppShell.Footer>
      )}

      <CreateGroupModal opened={createOpened} onClose={closeCreate} />
      <SearchModal opened={searchOpened} onClose={closeSearch} />
    </MantineAppShell>
  )
}
