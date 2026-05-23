import { useNavigate } from 'react-router-dom'
import {
  Badge,
  Group,
  Image,
  Loader,
  Paper,
  SimpleGrid,
  Skeleton,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import {
  IconAlbum,
  IconChartBar,
  IconMessageStar,
  IconTrophy,
  IconUsersGroup,
} from '@tabler/icons-react'
import AppShell from '../../components/layout/AppShell'
import ExploreNavTabs from '../../components/explore/ExploreNavTabs'
import { useSiteStats } from '../../hooks/useExplore'
import { ratingColor } from '../../utils/ratingColor'
import type { ArtistNominationItem, ExploreAlbumItem } from '../../types/explore'

// ==================== Stat card ====================

interface StatCardProps {
  label: string
  value: number
  icon: React.ReactNode
}

function StatCard({ label, value, icon }: StatCardProps) {
  return (
    <Paper withBorder p="md">
      <Group gap="sm" align="flex-start" wrap="nowrap">
        <Text c="dimmed">{icon}</Text>
        <div>
          <Text size="xl" fw={700} lh={1}>
            {value.toLocaleString()}
          </Text>
          <Text size="xs" c="dimmed" mt={4}>
            {label}
          </Text>
        </div>
      </Group>
    </Paper>
  )
}

// ==================== Ranked album row ====================


interface RankedAlbumRowProps {
  rank: number
  album: ExploreAlbumItem
  subtitle?: string
  onClick?: () => void
}

function RankedAlbumRow({ rank, album, subtitle, onClick }: RankedAlbumRowProps) {
  return (
    <Group
      justify="space-between"
      wrap="nowrap"
      onClick={onClick}
      style={{ cursor: onClick ? 'pointer' : undefined }}
    >
      <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
        <Text size="sm" c="dimmed" fw={500} w={20} ta="right" style={{ flexShrink: 0 }}>
          {rank}
        </Text>
        <Image
          src={album.cover_url ?? undefined}
          w={44}
          h={44}
          radius="sm"
          style={{ flexShrink: 0 }}
          fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='44' height='44'%3E%3Crect width='44' height='44' fill='%23373A40'/%3E%3C/svg%3E"
        />
        <div style={{ minWidth: 0 }}>
          <Text size="sm" fw={500} lineClamp={1}>{album.title}</Text>
          <Text size="xs" c="dimmed" lineClamp={1}>{album.artist}</Text>
          {subtitle && <Text size="xs" c="dimmed">{subtitle}</Text>}
        </div>
      </Group>
      {album.avg_rating != null && (
        <Badge color={ratingColor(album.avg_rating)} variant="filled" size="sm" style={{ flexShrink: 0 }}>
          {album.avg_rating.toFixed(1)}
        </Badge>
      )}
    </Group>
  )
}

// ==================== Ranked artist row ====================

interface RankedArtistRowProps {
  rank: number
  artist: ArtistNominationItem
}

function RankedArtistRow({ rank, artist }: RankedArtistRowProps) {
  return (
    <Group justify="space-between" wrap="nowrap">
      <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
        <Text size="sm" c="dimmed" fw={500} w={20} ta="right" style={{ flexShrink: 0 }}>
          {rank}
        </Text>
        <div style={{ minWidth: 0 }}>
          <Text size="sm" fw={500} lineClamp={1}>{artist.artist}</Text>
          <Text size="xs" c="dimmed">
            {artist.unique_albums} {artist.unique_albums === 1 ? 'album' : 'albums'}
          </Text>
        </div>
      </Group>
      <Badge color="violet" variant="light" size="sm" style={{ flexShrink: 0 }}>
        {artist.nomination_count} nominations
      </Badge>
    </Group>
  )
}

// ==================== Section ====================

interface RankedSectionProps {
  title: string
  children: React.ReactNode
  isLoading: boolean
}

function RankedSection({ title, children, isLoading }: RankedSectionProps) {
  return (
    <Paper withBorder p="md">
      <Text size="sm" fw={600} c="dimmed" tt="uppercase" mb="sm">
        {title}
      </Text>
      <Stack gap="sm">
        {isLoading
          ? Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} h={44} radius="sm" />)
          : children}
      </Stack>
    </Paper>
  )
}

// ==================== Page ====================

export default function ExploreStatsPage() {
  const navigate = useNavigate()
  const { data: stats, isLoading } = useSiteStats()

  return (
    <AppShell>
      <Stack gap="sm">
        <Group gap="xs" align="center">
          <IconChartBar size={22} />
          <Title order={3}>Explore</Title>
        </Group>

        <ExploreNavTabs />

        {/* Totals */}
        <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
          {isLoading ? (
            Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} h={80} radius="sm" />)
          ) : (
            <>
              <StatCard
                label="Albums Nominated"
                value={stats?.total_albums_nominated ?? 0}
                icon={<IconAlbum size={20} />}
              />
              <StatCard
                label="Reviews Recorded"
                value={stats?.total_reviews ?? 0}
                icon={<IconMessageStar size={20} />}
              />
              <StatCard
                label="Active Groups"
                value={stats?.total_active_groups ?? 0}
                icon={<IconUsersGroup size={20} />}
              />
              <StatCard
                label="Active Members"
                value={stats?.total_active_members ?? 0}
                icon={<IconTrophy size={20} />}
              />
            </>
          )}
        </SimpleGrid>

        {/* Ranked lists */}
        {isLoading ? (
          <Loader size="sm" mx="auto" mt="md" />
        ) : !stats ? null : (
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="sm">
            <RankedSection title="🏆 Top Rated Albums" isLoading={false}>
              {stats.top_rated_albums.length === 0 ? (
                <Text size="sm" c="dimmed">Not enough reviews yet.</Text>
              ) : (
                stats.top_rated_albums.map((album, i) => (
                  <RankedAlbumRow
                    key={album.id}
                    rank={i + 1}
                    album={album}
                    subtitle={`${album.review_count} reviews`}
                    onClick={() => navigate(`/albums/${album.id}`)}
                  />
                ))
              )}
            </RankedSection>

            <RankedSection title="🎤 Most Nominated Artists" isLoading={false}>
              {stats.most_nominated_artists.length === 0 ? (
                <Text size="sm" c="dimmed">No nominations yet.</Text>
              ) : (
                stats.most_nominated_artists.map((artist, i) => (
                  <RankedArtistRow key={artist.artist} rank={i + 1} artist={artist} />
                ))
              )}
            </RankedSection>

            <RankedSection title="📀 Most Nominated Albums" isLoading={false}>
              {stats.most_nominated_albums.length === 0 ? (
                <Text size="sm" c="dimmed">No nominations yet.</Text>
              ) : (
                stats.most_nominated_albums.map((album, i) => (
                  <RankedAlbumRow
                    key={album.id}
                    rank={i + 1}
                    album={album}
                    subtitle={`${album.nomination_count} nominations`}
                    onClick={() => navigate(`/albums/${album.id}`)}
                  />
                ))
              )}
            </RankedSection>

            <RankedSection title="📉 Lowest Rated Albums" isLoading={false}>
              {stats.bottom_rated_albums.length === 0 ? (
                <Text size="sm" c="dimmed">Not enough reviews yet.</Text>
              ) : (
                stats.bottom_rated_albums.map((album, i) => (
                  <RankedAlbumRow
                    key={album.id}
                    rank={i + 1}
                    album={album}
                    subtitle={`${album.review_count} reviews`}
                    onClick={() => navigate(`/albums/${album.id}`)}
                  />
                ))
              )}
            </RankedSection>
          </SimpleGrid>
        )}
      </Stack>
    </AppShell>
  )
}
