import { Button, Group, Stack, Text } from '@mantine/core'
import { Link } from 'react-router-dom'

export default function GuestReviewPrompt() {
  return (
    <Stack gap="sm" align="flex-start">
      <Text size="sm" c="dimmed">Log in to rate this album and guess who picked it.</Text>
      <Group gap="xs">
        <Button component={Link} to="/login">Log in</Button>
        <Button variant="light" component={Link} to="/register">Register</Button>
      </Group>
    </Stack>
  )
}
