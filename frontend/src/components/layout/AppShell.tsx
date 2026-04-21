import { Link, useNavigate, useLocation } from 'react-router-dom'
import {
  ActionIcon,
  AppShell as MantineAppShell,
  Avatar,
  Burger,
  Button,
  Group,
  Menu,
  NavLink,
  ScrollArea,
  Skeleton,
  Text,
  Title,
  UnstyledButton,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import {
  IconDisc,
  IconLayoutSidebarLeftCollapse,
  IconLayoutSidebarLeftExpand,
  IconLogout,
  IconPlus,
  IconSearch,
  IconUser,
} from '@tabler/icons-react'
import { useAuth } from '../../hooks/useAuth'
import { useMyGroups } from '../../hooks/useGroups'
import CreateGroupModal from '../groups/CreateGroupModal'
import JoinGroupModal from '../groups/JoinGroupModal'

interface AppShellProps {
  children: React.ReactNode
}

export default function AppShell({ children }: AppShellProps) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileOpened, { toggle: toggleMobile }] = useDisclosure()
  const [desktopOpened, { toggle: toggleDesktop }] = useDisclosure(true)
  const [createOpened, { open: openCreate, close: closeCreate }] = useDisclosure()
  const [joinOpened, { open: openJoin, close: closeJoin }] = useDisclosure()

  const { data: groups, isLoading } = useMyGroups(user?.username ?? '')

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
            onClick={openJoin}
          >
            Find group
          </Button>
        </MantineAppShell.Section>

        <MantineAppShell.Section grow component={ScrollArea} mt="md">
          <Text size="xs" fw={600} c="dimmed" mb="xs" tt="uppercase">
            Your Groups
          </Text>
          {isLoading
            ? Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} h={32} mb={4} radius="sm" />)
            : groups?.map((g) => (
                <NavLink
                  key={g.id}
                  label={g.name}
                  component={Link}
                  to={`/groups/${g.id}`}
                  active={location.pathname.startsWith(`/groups/${g.id}`)}
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

      <CreateGroupModal opened={createOpened} onClose={closeCreate} />
      <JoinGroupModal opened={joinOpened} onClose={closeJoin} />
    </MantineAppShell>
  )
}
