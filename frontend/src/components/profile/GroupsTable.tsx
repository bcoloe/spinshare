import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Avatar,
  Badge,
  Button,
  Group,
  Loader,
  Skeleton,
  Stack,
  Table,
  Text,
  UnstyledButton,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useQuery } from '@tanstack/react-query'
import { IconChevronDown, IconChevronRight } from '@tabler/icons-react'
import { useJoinGroup } from '../../hooks/useGroups'
import { groupService } from '../../services/groupService'
import { ApiError } from '../../services/apiClient'
import type { UserGroupItem } from '../../types/auth'

interface GroupRowProps {
  group: UserGroupItem
}

function GroupRow({ group }: GroupRowProps) {
  const [expanded, setExpanded] = useState(false)
  const navigate = useNavigate()
  const joinGroup = useJoinGroup()
  const inCommon = group.current_user_role !== null

  const { data: members = [], isFetching: membersFetching } = useQuery({
    queryKey: ['groups', group.id, 'members'],
    queryFn: () => groupService.getMembers(group.id),
    enabled: expanded,
  })

  const handleJoin = async (e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await joinGroup.mutateAsync(group.id)
      notifications.show({ color: 'green', message: `Joined "${group.name}"` })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not join group'
      notifications.show({ color: 'red', message })
    }
  }

  return (
    <>
      <Table.Tr
        style={{ cursor: 'pointer' }}
        onClick={() => setExpanded((v) => !v)}
      >
        <Table.Td w={28}>
          {expanded ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
        </Table.Td>
        <Table.Td>
          <Text
            size="sm"
            fw={inCommon ? 700 : 400}
            c={inCommon ? 'green.4' : undefined}
          >
            {group.name}
          </Text>
        </Table.Td>
        <Table.Td>
          <Text size="sm" c="dimmed">
            {group.member_count} member{group.member_count !== 1 ? 's' : ''}
          </Text>
        </Table.Td>
        <Table.Td>
          {inCommon ? (
            <Badge size="sm" variant="light" color="green">
              {group.current_user_role}
            </Badge>
          ) : (
            <Button
              size="xs"
              variant="light"
              loading={joinGroup.isPending}
              onClick={handleJoin}
            >
              Join
            </Button>
          )}
        </Table.Td>
      </Table.Tr>

      {expanded && (
        <Table.Tr>
          <Table.Td />
          <Table.Td
            colSpan={3}
            style={{ background: 'var(--mantine-color-dark-7)', padding: '10px 16px' }}
          >
            {membersFetching ? (
              <Loader size="xs" />
            ) : members.length === 0 ? (
              <Text size="xs" c="dimmed">No members found.</Text>
            ) : (
              <Group gap="xs" wrap="wrap">
                {members.map((m) => (
                  <UnstyledButton
                    key={m.user_id}
                    onClick={(e) => { e.stopPropagation(); navigate(`/users/${m.username}`) }}
                  >
                    <Group gap={6}>
                      <Avatar size="xs" radius="xl" color="violet">
                        {m.username[0].toUpperCase()}
                      </Avatar>
                      <Text
                        size="xs"
                        onMouseEnter={(e) => { e.currentTarget.style.textDecoration = 'underline' }}
                        onMouseLeave={(e) => { e.currentTarget.style.textDecoration = 'none' }}
                      >
                        {m.username}
                      </Text>
                    </Group>
                  </UnstyledButton>
                ))}
              </Group>
            )}
          </Table.Td>
        </Table.Tr>
      )}
    </>
  )
}

interface Props {
  groups: UserGroupItem[]
  loading: boolean
}

export default function GroupsTable({ groups, loading }: Props) {
  if (loading) {
    return (
      <Stack gap="xs">
        {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} h={44} radius="sm" />)}
      </Stack>
    )
  }

  if (groups.length === 0) {
    return <Text size="sm" c="dimmed">No public groups.</Text>
  }

  const sorted = [...groups].sort((a, b) => {
    // shared groups first, then alphabetical
    if ((a.current_user_role !== null) !== (b.current_user_role !== null)) {
      return a.current_user_role !== null ? -1 : 1
    }
    return a.name.localeCompare(b.name)
  })

  return (
    <Table highlightOnHover verticalSpacing="sm">
      <Table.Thead>
        <Table.Tr>
          <Table.Th w={28} />
          <Table.Th><Text size="xs" c="dimmed">Name</Text></Table.Th>
          <Table.Th><Text size="xs" c="dimmed">Members</Text></Table.Th>
          <Table.Th />
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {sorted.map((g) => (
          <GroupRow key={g.id} group={g} />
        ))}
      </Table.Tbody>
    </Table>
  )
}
