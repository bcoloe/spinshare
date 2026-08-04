import { Box, Button, Group, Stack, Title, Tooltip } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { IconPlus } from '@tabler/icons-react'
import MyNominationsPool from './MyNominationsPool'
import AlbumSearchModal from '../albums/AlbumSearchModal'
import { useAuth } from '../../hooks/useAuth'
import { useMyGroups } from '../../hooks/useGroups'

const ROLE_RANK: Record<string, number> = { owner: 0, admin: 1, member: 2 }

export default function MyNominationsPanel() {
  const { user } = useAuth()
  const { data: groups } = useMyGroups(user?.username ?? '')
  const [nominateOpened, { open: openNominate, close: closeNominate }] = useDisclosure(false)

  const canNominateAnyGroup = (groups ?? []).some((g) => {
    if (!g.current_user_role) return false
    const minRole = g.settings?.min_role_to_nominate ?? 'member'
    return (ROLE_RANK[g.current_user_role] ?? 99) <= (ROLE_RANK[minRole] ?? 99)
  })

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="center">
        <Title order={5}>My Nominations</Title>
        <Tooltip
          label="You don't have permission to nominate in any of your groups"
          disabled={canNominateAnyGroup}
        >
          <Box component="span" style={canNominateAnyGroup ? undefined : { cursor: 'not-allowed' }}>
            <Button
              leftSection={<IconPlus size={16} />}
              size="sm"
              onClick={openNominate}
              disabled={!canNominateAnyGroup}
              style={canNominateAnyGroup ? undefined : { pointerEvents: 'none' }}
            >
              Add Nomination
            </Button>
          </Box>
        </Tooltip>
      </Group>
      <MyNominationsPool />

      <AlbumSearchModal opened={nominateOpened} onClose={closeNominate} />
    </Stack>
  )
}
