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
import { useInvitation, useAcceptInvitation } from '../hooks/useGroups'
import { ApiError } from '../services/apiClient'

export default function InviteAcceptPage() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const { user, isInitializing } = useAuth()
  const { data: invitation, isLoading, error } = useInvitation(token ?? '')
  const acceptInvitation = useAcceptInvitation()

  const handleAccept = async () => {
    if (!token) return
    try {
      const inv = await acceptInvitation.mutateAsync(token)
      notifications.show({ color: 'green', message: `You joined ${inv.group_name}!` })
      navigate(`/groups/${inv.group_id}`)
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not accept invitation'
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

  const inviteError = error instanceof ApiError ? error : null

  if (!invitation || inviteError) {
    const detail = inviteError?.status === 404
      ? 'This invitation link is invalid or has been revoked.'
      : 'Something went wrong loading this invitation.'

    return (
      <Center h="100vh">
        <Box w={400} ta="center">
          <Title order={3} mb="sm">Invitation not found</Title>
          <Text c="dimmed" size="sm" mb="xl">{detail}</Text>
          <Anchor component={Link} to="/">Go to SpinShare</Anchor>
        </Box>
      </Center>
    )
  }

  if (invitation.status === 'accepted') {
    return (
      <Center h="100vh">
        <Box w={400} ta="center">
          <Title order={3} mb="sm">Already accepted</Title>
          <Text c="dimmed" size="sm" mb="xl">
            This invitation has already been used.
          </Text>
          <Anchor component={Link} to={`/groups/${invitation.group_id}`}>
            Go to {invitation.group_name}
          </Anchor>
        </Box>
      </Center>
    )
  }

  if (invitation.status === 'expired') {
    return (
      <Center h="100vh">
        <Box w={400} ta="center">
          <Title order={3} mb="sm">Invitation expired</Title>
          <Text c="dimmed" size="sm" mb="xl">
            This invitation has expired. Ask {invitation.inviter_username} to send a new one.
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
            {invitation.inviter_username} invited you to join a group on SpinShare
          </Text>
        </Stack>
        <Paper withBorder p="xl" radius="md">
          <Stack gap="md" align="center">
            <Title order={3}>{invitation.group_name}</Title>
            {user ? (
              <>
                <Text size="sm" c="dimmed">
                  Signing in as <strong>{user.username}</strong>
                </Text>
                {user.email !== invitation.invited_email && (
                  <Text size="xs" c="orange">
                    Note: this invitation was sent to {invitation.invited_email}. Make sure
                    you're signed in with that account.
                  </Text>
                )}
                <Button
                  fullWidth
                  loading={acceptInvitation.isPending}
                  onClick={handleAccept}
                >
                  Accept invitation
                </Button>
              </>
            ) : (
              <>
                <Text size="sm" c="dimmed" ta="center">
                  Sign in or create an account to accept this invitation.
                </Text>
                <Button
                  fullWidth
                  component={Link}
                  to={`/login?next=/invite/${token}`}
                >
                  Sign in
                </Button>
                <Anchor
                  component={Link}
                  to={`/register?next=/invite/${token}`}
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
