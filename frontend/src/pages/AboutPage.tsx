import { Divider, Group, Paper, SimpleGrid, Stack, Text, Title } from '@mantine/core'
import { IconBook, IconBrandGithub } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/layout/AppShell'

export default function AboutPage() {
  const navigate = useNavigate()

  return (
    <AppShell>
      <Stack gap="xl" maw={720}>
        <Stack gap="xs">
          <Title order={2}>About SpinShare</Title>
          <Text c="dimmed" size="sm">Music is better when it&apos;s shared.</Text>
        </Stack>

        <Stack gap="md">
          <Text>
            SpinShare is a group-based music sharing platform built around the belief that
            listening is richer when done together. Gather friends into a listening group,
            each person nominates albums they love, and every day a random album from the
            group&apos;s shared catalog is chosen as the day&apos;s spin — something for everyone to
            listen to, review, and discuss.
          </Text>
          <Text>
            The randomized format cuts through algorithmic fatigue and puts discovery back
            in the hands of people you trust. You might end up loving something you never
            would have found on your own — and the best part is knowing exactly which friend
            recommended it.
          </Text>
          <Text>
            SpinShare connects to your favorite streaming service so you can listen directly
            from the app, and over time builds a picture of your listening habits through
            reviews, nomination guesses, and group stats.
          </Text>
        </Stack>

        <Divider />

        <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="md">
          <Paper
            withBorder
            p="lg"
            style={{ cursor: 'pointer' }}
            onClick={() => navigate('/about/getting-started')}
          >
            <Stack gap="sm">
              <Group gap="xs">
                <IconBook size={18} />
                <Text fw={600}>Getting Started</Text>
              </Group>
              <Text size="sm" c="dimmed">
                New to SpinShare? Learn how to navigate the site, join or create groups,
                connect your audio service, and make the most of reviews and stats.
              </Text>
              <Text size="sm" c="violet" fw={500}>Read the guide →</Text>
            </Stack>
          </Paper>

          <Paper
            withBorder
            p="lg"
            style={{ cursor: 'pointer' }}
            onClick={() => navigate('/about/contributing')}
          >
            <Stack gap="sm">
              <Group gap="xs">
                <IconBrandGithub size={18} />
                <Text fw={600}>Contributing</Text>
              </Group>
              <Text size="sm" c="dimmed">
                SpinShare is open source. Find out how to report issues, suggest features,
                or contribute code on GitHub.
              </Text>
              <Text size="sm" c="violet" fw={500}>View on GitHub →</Text>
            </Stack>
          </Paper>
        </SimpleGrid>
      </Stack>
    </AppShell>
  )
}
