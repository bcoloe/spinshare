import { Button, Divider, Group, Stack, Text, Title } from '@mantine/core'
import { IconBook, IconLogin, IconUserPlus } from '@tabler/icons-react'
import { Link } from 'react-router-dom'
import AppShell from '../components/layout/AppShell'
import { PublicSpin } from '../components/spin/TodaysSpin'

export default function LandingPage() {
  return (
    <AppShell>
      <Stack gap="xl" maw={960} mx="auto">
        <Stack gap="xs" ta="center" align="center">
          <Title order={1}>SpinShare</Title>
          <Text c="dimmed" size="lg" maw={560}>
            Groups roll a random album from what members nominate — you review it, then guess
            who picked it.
          </Text>
          <Group gap="sm" mt="sm">
            <Button component={Link} to="/login" leftSection={<IconLogin size={16} />}>
              Log in
            </Button>
            <Button component={Link} to="/register" variant="light" leftSection={<IconUserPlus size={16} />}>
              Register
            </Button>
            <Button component={Link} to="/about/getting-started" variant="subtle" leftSection={<IconBook size={16} />}>
              See how it works
            </Button>
          </Group>
        </Stack>

        <Divider label="Today's roll" labelPosition="center" />

        <PublicSpin />

        <Divider />

        <Stack gap="xs" ta="center" align="center" mb="xl">
          <Text size="sm">
            Want to form your own group, nominate albums, and build a review history?
          </Text>
          <Group gap="md">
            <Text component={Link} to="/about" size="sm" c="violet" fw={500}>
              Learn more about SpinShare →
            </Text>
            <Text component={Link} to="/about/getting-started" size="sm" c="violet" fw={500}>
              Read the getting started guide →
            </Text>
          </Group>
        </Stack>
      </Stack>
    </AppShell>
  )
}
