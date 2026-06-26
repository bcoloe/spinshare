import { useNavigate, useLocation } from 'react-router-dom'
import { Tabs } from '@mantine/core'
import { IconChartBar, IconDisc, IconUsers, IconUsersGroup } from '@tabler/icons-react'

export default function ExploreNavTabs() {
  const navigate = useNavigate()
  const { pathname } = useLocation()

  const activeTab = pathname.startsWith('/explore/groups')
    ? 'groups'
    : pathname.startsWith('/explore/users')
      ? 'users'
      : pathname.startsWith('/explore/stats')
        ? 'stats'
        : 'albums'

  return (
    <Tabs value={activeTab} onChange={(v) => v && navigate(`/explore/${v}`)} mb="md">
      <Tabs.List>
        <Tabs.Tab value="albums" leftSection={<IconDisc size={14} />}>
          Albums
        </Tabs.Tab>
        <Tabs.Tab value="groups" leftSection={<IconUsersGroup size={14} />}>
          Groups
        </Tabs.Tab>
        <Tabs.Tab value="users" leftSection={<IconUsers size={14} />}>
          Users
        </Tabs.Tab>
        <Tabs.Tab value="stats" leftSection={<IconChartBar size={14} />}>
          Stats
        </Tabs.Tab>
      </Tabs.List>
    </Tabs>
  )
}
