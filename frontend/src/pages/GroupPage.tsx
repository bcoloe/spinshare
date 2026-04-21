import { useParams, useNavigate } from 'react-router-dom'
import {
  Badge,
  Button,
  Divider,
  Group,
  Skeleton,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { IconDisc } from '@tabler/icons-react'
import AppShell from '../components/layout/AppShell'
import MemberList from '../components/groups/MemberList'
import { useGroup } from '../hooks/useGroups'

const ROLE_COLOR = { owner: 'violet', admin: 'blue', member: 'gray' } as const

export default function GroupPage() {
  const { groupId } = useParams<{ groupId: string }>()
  const navigate = useNavigate()
  const { data: group, isLoading } = useGroup(Number(groupId))

  return (
    <AppShell>
      <Stack gap="lg" maw={640}>
        {isLoading ? (
          <Skeleton h={40} w={200} />
        ) : (
          <>
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
                  {group?.is_public ? 'Public' : 'Private'} · {group?.member_count} member{group?.member_count !== 1 ? 's' : ''}
                </Text>
              </div>
              <Button
                leftSection={<IconDisc size={16} />}
                onClick={() => navigate(`/groups/${groupId}/spin`)}
              >
                Today&apos;s spin
              </Button>
            </Group>

            <Divider />

            <div>
              <Title order={5} mb="sm">Members</Title>
              {group && <MemberList group={group} />}
            </div>
          </>
        )}
      </Stack>
    </AppShell>
  )
}
