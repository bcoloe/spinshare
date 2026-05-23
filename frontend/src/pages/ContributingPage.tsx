import { Anchor, Code, Divider, Group, Stack, Text, Title } from '@mantine/core'
import { IconArrowLeft, IconBrandGithub, IconBug, IconGitPullRequest, IconStar } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/layout/AppShell'

const GITHUB_URL = 'https://github.com/bcoloe/spinshare'

export default function ContributingPage() {
  const navigate = useNavigate()

  return (
    <AppShell>
      <Stack gap="xl" maw={720}>

        {/* Back link */}
        <Anchor
          component="button"
          size="sm"
          c="dimmed"
          onClick={() => navigate('/about')}
          style={{ display: 'flex', alignItems: 'center', gap: 4 }}
        >
          <IconArrowLeft size={14} />
          Back to About
        </Anchor>

        {/* Header */}
        <Stack gap="xs">
          <Title order={2}>Contributing</Title>
          <Text c="dimmed" size="sm">
            SpinShare is an open-source project and welcomes contributions of all kinds.
          </Text>
        </Stack>

        {/* GitHub link */}
        <Anchor
          href={GITHUB_URL}
          target="_blank"
          rel="noopener noreferrer"
          style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
          fw={500}
        >
          <IconBrandGithub size={18} />
          github.com/bcoloe/spinshare
        </Anchor>

        <Divider />

        {/* Reporting bugs */}
        <Stack gap="sm">
          <Group gap="xs" align="center">
            <Text c="violet"><IconBug size={18} /></Text>
            <Title order={4}>Reporting Bugs</Title>
          </Group>
          <Text size="sm" pl={28}>
            Found something broken? Open an issue on the{' '}
            <Anchor href={`${GITHUB_URL}/issues`} target="_blank" rel="noopener noreferrer">
              GitHub Issues
            </Anchor>{' '}
            page. Please include steps to reproduce the bug, what you expected to happen, and
            what actually happened. Screenshots or console errors are always helpful.
          </Text>
        </Stack>

        <Divider />

        {/* Feature requests */}
        <Stack gap="sm">
          <Group gap="xs" align="center">
            <Text c="violet"><IconStar size={18} /></Text>
            <Title order={4}>Suggesting Features</Title>
          </Group>
          <Text size="sm" pl={28}>
            Have an idea for SpinShare? Open a GitHub Issue with the{' '}
            <Code>enhancement</Code> label and describe the feature and the problem it solves.
            Discussion happens in the issue thread before any code is written, so feel free to
            propose ideas early.
          </Text>
        </Stack>

        <Divider />

        {/* Contributing code */}
        <Stack gap="sm">
          <Group gap="xs" align="center">
            <Text c="violet"><IconGitPullRequest size={18} /></Text>
            <Title order={4}>Contributing Code</Title>
          </Group>
          <Stack gap="xs" pl={28}>
            <Text size="sm">
              Ready to write some code? Here&apos;s the workflow:
            </Text>
            <Stack gap={6} pl={8}>
              <Text size="sm">1. Fork the repository on GitHub.</Text>
              <Text size="sm">2. Create a feature branch off <Code>main</Code>.</Text>
              <Text size="sm">
                3. Make your changes. Backend logic lives in <Code>backend/app/services/</Code>;
                frontend pages and components in <Code>frontend/src/</Code>.
              </Text>
              <Text size="sm">
                4. Add or update tests — backend tests use pytest and live alongside source files
                with a <Code>_test.py</Code> suffix.
              </Text>
              <Text size="sm">5. Open a pull request against <Code>main</Code> with a clear description of what changed and why.</Text>
            </Stack>
            <Text size="sm" mt={4}>
              For larger changes, open an issue first so the approach can be discussed before
              investing significant effort.
            </Text>
          </Stack>
        </Stack>

      </Stack>
    </AppShell>
  )
}
