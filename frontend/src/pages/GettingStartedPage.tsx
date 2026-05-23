import { Anchor, Badge, Code, Divider, Group, Stack, Text, Title } from '@mantine/core'
import {
  IconArrowLeft,
  IconBell,
  IconChartBar,
  IconDisc,
  IconMusic,
  IconPlus,
  IconSearch,
  IconStar,
  IconUsersGroup,
} from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import AppShell from '../components/layout/AppShell'

// ─── Section ────────────────────────────────────────────────────────────────

interface SectionProps {
  icon: React.ReactNode
  title: string
  children: React.ReactNode
}

function Section({ icon, title, children }: SectionProps) {
  return (
    <Stack gap="sm">
      <Group gap="xs" align="center">
        <Text c="violet">{icon}</Text>
        <Title order={4}>{title}</Title>
      </Group>
      <Stack gap="xs" pl={28}>
        {children}
      </Stack>
    </Stack>
  )
}

// ─── Inline label ────────────────────────────────────────────────────────────

function Label({ children }: { children: React.ReactNode }) {
  return (
    <Badge variant="light" color="violet" size="sm" radius="sm" style={{ fontWeight: 500 }}>
      {children}
    </Badge>
  )
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function GettingStartedPage() {
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
          <Title order={2}>Getting Started</Title>
          <Text c="dimmed" size="sm">
            A walkthrough of SpinShare — from joining your first group to tracking your stats.
          </Text>
        </Stack>

        <Divider />

        {/* 1. How SpinShare Works */}
        <Section icon={<IconDisc size={18} />} title="How SpinShare Works">
          <Text size="sm">
            SpinShare is organised around <strong>listening groups</strong>. Each group has a shared
            album catalog built from nominations submitted by its members. Every day, an album is
            randomly selected from that catalog as the group&apos;s <strong>spin of the day</strong>.
          </Text>
          <Text size="sm">
            Members are expected to listen to the spin, write a short review, rate it, and guess
            which member nominated it. Over time this builds a rich record of everyone&apos;s listening
            history and taste.
          </Text>
        </Section>

        <Divider />

        {/* 2. Site Layout */}
        <Section icon={<IconSearch size={18} />} title="Navigating the App">
          <Text size="sm">
            The <strong>sidebar</strong> on the left is your main navigation hub:
          </Text>
          <Stack gap={6} pl={8}>
            <Text size="sm">
              <Label>Search</Label>{' '}
              Find users and groups across the platform.
            </Text>
            <Text size="sm">
              <Label>Explore → Albums</Label>{' '}
              Browse all publicly reviewed albums and top-rated picks.
            </Text>
            <Text size="sm">
              <Label>Explore → Groups</Label>{' '}
              Discover public listening groups you can join.
            </Text>
            <Text size="sm">
              <Label>Explore → Stats</Label>{' '}
              Site-wide listening stats, most-reviewed albums, and top nominators.
            </Text>
            <Text size="sm">
              <Label>Your Groups</Label>{' '}
              Quick links to every group you belong to. Star one to make it your default landing page.
            </Text>
          </Stack>
          <Text size="sm" mt={4}>
            The <strong>avatar menu</strong> (top right) takes you to your Profile, where you can
            edit account details, connect streaming services, and view your personal stats.
          </Text>
        </Section>

        <Divider />

        {/* 3. Finding & Joining Groups */}
        <Section icon={<IconUsersGroup size={18} />} title="Finding and Joining Groups">
          <Text size="sm">
            To find a group, open <Label>Explore → Groups</Label> in the sidebar. You can browse
            all publicly listed groups and filter by name. Groups marked as open allow you to join
            directly; others require an invitation from a current member.
          </Text>
          <Text size="sm">
            If someone shares an invite link with you, visiting that link will walk you through
            accepting it — no searching required. Pending invitations also appear in the{' '}
            <strong>notification bell</strong> (🔔) at the top of the page, where you can accept
            or decline them.
          </Text>
        </Section>

        <Divider />

        {/* 4. Inviting Members */}
        <Section icon={<IconBell size={18} />} title="Inviting Members to Your Group">
          <Text size="sm">
            Group members can invite new members from the group page. Navigate to your
            group, open the <Label>Members</Label> tab, and use the <strong>Invite member</strong>{' '}
            button to search for a user by username. Exactly <em>who</em> can invite members is controlled
            at the group settings level; by default only Owners and Admins may.
          </Text>
          <Text size="sm">
            The invited user will receive a notification in their bell icon. They can accept or
            decline the invitation from there. Group settings also control whether the group is
            listed publicly and whether members can join without an invitation.
          </Text>
          <Text size="sm">
            To invite new users to SpinShare, generate a sharable link and send it to whomever. This will
            direct them register a new account and automatically add them to the group once created.
          </Text>
        </Section>

        <Divider />

        {/* 5. Nominating Albums */}
        <Section icon={<IconPlus size={18} />} title="Nominating Albums">
          <Text size="sm">
            Nominations are the fuel that drives SpinShare. Every album in a group&apos;s catalog was
            put there by a member who wanted the group to hear it. The nomination modal offers three
            ways to add an album:
          </Text>

          <Stack gap="xs" pl={8}>
            <Stack gap={4}>
              <Text size="sm" fw={600}>Search</Text>
              <Text size="sm">
                Type an album or artist name in the <Label>Search</Label> tab. SpinShare queries
                Spotify and Apple Music simultaneously and surfaces deduplicated results from both,
                so you&apos;ll find albums regardless of which service originally published them.
              </Text>
            </Stack>

            <Stack gap={4}>
              <Text size="sm" fw={600}>Paste a URL</Text>
              <Text size="sm">
                Switch to the <Label>URL</Label> tab and paste a link directly from your streaming
                service. SpinShare will resolve the album automatically. Supported URL formats:
              </Text>
              <Stack gap={4} pl={8}>
                <Text size="sm">
                  <Label>Spotify</Label>{' '}
                  <Code>open.spotify.com/album/…</Code>
                </Text>
                <Text size="sm">
                  <Label>Apple Music</Label>{' '}
                  <Code>music.apple.com/…/album/…</Code>
                </Text>
                <Text size="sm">
                  <Label>YouTube Music</Label>{' '}
                  <Code>music.youtube.com/browse/…</Code> or{' '}
                  <Code>music.youtube.com/playlist?list=…</Code>
                </Text>
                <Text size="sm">
                  <Label>Bandcamp</Label>{' '}
                  <Code>artist.bandcamp.com/album/…</Code> — SpinShare scrapes the page for
                  metadata. If it can&apos;t parse the page automatically, a fallback form lets you
                  enter the artist and album title manually.
                </Text>
              </Stack>
            </Stack>

            <Stack gap={4}>
              <Text size="sm" fw={600}>Your nomination pool</Text>
              <Text size="sm">
                The <Label>Pool</Label> tab shows every album you&apos;ve previously nominated in
                any group. Use it to quickly re-nominate a favorite to a new group without
                searching again — albums you&apos;ve already nominated to the current group are
                filtered out automatically.
              </Text>
            </Stack>
          </Stack>

          <Text size="sm" mt={4}>
            The <strong>Nominate</strong> button appears on the group&apos;s Catalog page, on the
            Today&apos;s Spin page, and on the Dashboard in your My Nominations panel. Group
            settings may restrict who can nominate (owners only, admins and above, or all members)
            and can cap the number of nominations allowed per day.
          </Text>
        </Section>

        <Divider />

        {/* 6. Favoriting a Group */}
        <Section icon={<IconStar size={18} />} title="Favoriting a Group">
          <Text size="sm">
            You can mark one group as your <strong>favorite</strong> so that SpinShare takes you
            straight to it when you open the app. To set a favorite, click the{' '}
            <strong>⭐ star icon</strong> next to a group in the sidebar or on the Dashboard.
            Clicking it again removes the favorite.
          </Text>
          <Text size="sm">
            Only one group can be favorited at a time. Without a favorite set, SpinShare lands on
            the Dashboard showing all your groups.
          </Text>
        </Section>

        <Divider />

        {/* 6. Connecting Audio Services */}
        <Section icon={<IconMusic size={18} />} title="Connecting Audio Services">
          <Text size="sm">
            SpinShare can connect to streaming services so you can play albums directly in the app
            via the player bar at the bottom of the page.
          </Text>
          <Text size="sm">
            To connect a service, go to your <strong>Profile</strong> (avatar menu → Profile) and
            scroll to the <Label>Services</Label> section. From there you can:
          </Text>
          <Stack gap={6} pl={8}>
            <Text size="sm">
              <Label>Spotify</Label>{' '}
              Authenticate with your Spotify account. Requires a Spotify Premium subscription for
              in-app playback via the Web Playback SDK.
            </Text>
            <Text size="sm">
              <Label>Apple Music</Label>{' '}
              Connect your Apple Music account to link your library.
            </Text>
          </Stack>
          <Text size="sm" mt={4}>
            Once connected, the player bar will appear whenever you navigate to an album or start
            a spin, letting you control playback without leaving SpinShare.
          </Text>
        </Section>

        <Divider />

        {/* 7. Today's Spin */}
        <Section icon={<IconDisc size={18} />} title="Today's Spin">
          <Text size="sm">
            Each day, SpinShare selects one album from the group&apos;s catalog as the spin of
            the day. Navigate to your group and select <Label>Today&apos;s Spin</Label> to see
            the current album.
          </Text>
          <Text size="sm">
            From the spin page you can play the album (if a streaming service is connected),
            write your review, and submit your guess for who nominated it. Your guess is revealed
            once submitted — and you can see how other members guessed in the Review History.
          </Text>
        </Section>

        <Divider />

        {/* 8. Reviews and Guesses */}
        <Section icon={<IconDisc size={18} />} title="Reviews and Guesses">
          <Text size="sm">
            A review consists of a <strong>written take</strong> on the album and a <strong>numerical
            rating</strong> from 1 to 10. Reviews can be edited after submission, so don&apos;t worry
            about getting it perfect the first time.
          </Text>
          <Text size="sm">
            When you submit a guess, SpinShare tells you immediately whether you were right. All
            reviews and guess results for past spins are visible in the <Label>Review History</Label>{' '}
            tab on the group page, so you can look back at previous albums and compare notes.
          </Text>
        </Section>

        <Divider />

        {/* 9. Stats */}
        <Section icon={<IconChartBar size={18} />} title="Stats and History">
          <Text size="sm">
            SpinShare tracks a range of listening statistics at different levels:
          </Text>
          <Stack gap={6} pl={8}>
            <Text size="sm">
              <Label>Explore → Stats</Label>{' '}
              Site-wide numbers — total spins, most-reviewed albums, highest-rated picks, and
              top nominators across all groups.
            </Text>
            <Text size="sm">
              <Label>Profile → Stats</Label>{' '}
              Your personal record — total reviews written, average rating given, guess accuracy,
              and your nominated albums&apos; average scores.
            </Text>
            <Text size="sm">
              <Label>Group → Info tab</Label>{' '}
              Group-level stats including member activity, top-rated albums, and catalog size.
            </Text>
          </Stack>
        </Section>

      </Stack>
    </AppShell>
  )
}
