import { useNavigate, useParams, Link } from 'react-router-dom'
import {
  Anchor,
  Box,
  Button,
  Center,
  Loader,
  Paper,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useAuth } from '../hooks/useAuth'
import { useInviteLink, useAcceptInviteLink } from '../hooks/useGroups'
import { ApiError } from '../services/apiClient'

export default function JoinGroupPage() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const { user, isInitializing } = useAuth()
  const { data: link, isLoading, error } = useInviteLink(token ?? '')
  const acceptInviteLink = useAcceptInviteLink()

  const handleJoin = async () => {
    if (!token) return
    try {
      const joined = await acceptInviteLink.mutateAsync(token)
      notifications.show({ color: 'green', message: `You joined ${joined.group_name}!` })
      navigate(`/groups/${joined.group_id}`)
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not join group'
      notifications.show({ color: 'red', message })
    }
  }

  if (isInitializing || isLoading) {
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )
  }

  const linkError = error instanceof ApiError ? error : null

  if (!link || linkError) {
    return (
      <Center h="100vh">
        <Box w={400} ta="center">
          <Title order={3} mb="sm">Link not found</Title>
          <Text c="dimmed" size="sm" mb="xl">
            This invite link is invalid or has been revoked.
          </Text>
          <Anchor component={Link} to="/">Go to SpinShare</Anchor>
        </Box>
      </Center>
    )
  }

  return (
    <Center h="100vh">
      <Box w={400}>
        <Stack gap="xs" mb="xl" ta="center">
          <Title order={2}>You're invited!</Title>
          <Text c="dimmed" size="sm">
            {link.creator_username} invited you to join a group on SpinShare
          </Text>
        </Stack>
        <Paper withBorder p="xl" radius="md">
          <Stack gap="md" align="center">
            <Title order={3}>{link.group_name}</Title>
            {user ? (
              <>
                <Text size="sm" c="dimmed">
                  Joining as <strong>{user.username}</strong>
                </Text>
                <Button
                  fullWidth
                  loading={acceptInviteLink.isPending}
                  onClick={handleJoin}
                >
                  Join group
                </Button>
              </>
            ) : (
              <>
                <Text size="sm" c="dimmed" ta="center">
                  Sign in or create an account to join this group.
                </Text>
                <Button
                  fullWidth
                  component={Link}
                  to={`/login?next=/join/${token}`}
                >
                  Sign in
                </Button>
                <Anchor
                  component={Link}
                  to={`/register?next=/join/${token}`}
                  size="sm"
                >
                  No account? Register here
                </Anchor>
              </>
            )}
          </Stack>
        </Paper>
      </Box>
    </Center>
  )
}
