import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Anchor,
  Badge,
  Box,
  Card,
  Group,
  Image,
  Progress,
  Select,
  SimpleGrid,
  Skeleton,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from '@mantine/core'
import { IconMoodSad, IconTrophy } from '@tabler/icons-react'
import { useGroupRecaps } from '../../hooks/useRecaps'
import type { GuessAccuracy, LeaderboardEntry, RecapAlbumCard, RecapResponse } from '../../types/recap'

const BAR_COLORS = [
  '#7950f2', '#228be6', '#12b886', '#fd7e14', '#f06595',
  '#fab005', '#4dabf7', '#38d9a9', '#e599f7', '#a9e34b',
]

// Parse a "YYYY-MM-DD" API date as a local calendar date (avoids UTC day-shift).
function parseDate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function fmtDay(date: Date): string {
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

// week_end is exclusive (next Monday), so the inclusive last day is one earlier.
function formatWeekRange(weekStart: string, weekEnd: string): string {
  const start = parseDate(weekStart)
  const end = parseDate(weekEnd)
  end.setDate(end.getDate() - 1)
  return `${fmtDay(start)} – ${fmtDay(end)}`
}

interface LeaderboardProps {
  title: string
  entries: LeaderboardEntry[]
  unit: string
}

function Leaderboard({ title, entries, unit }: LeaderboardProps) {
  const max = entries.length ? Math.max(...entries.map((e) => e.count)) : 0
  return (
    <div>
      <Title order={6} mb="xs">{title}</Title>
      {entries.length === 0 ? (
        <Text size="sm" c="dimmed">No activity this week.</Text>
      ) : (
        <Stack gap="sm">
          {entries.map((entry, i) => (
            <Group key={entry.username} gap="sm" wrap="nowrap">
              <Text size="sm" c="dimmed" w={18} ta="right">{i + 1}</Text>
              <Box style={{ flex: 1, minWidth: 0 }}>
                <Group justify="space-between" gap="xs" mb={2} wrap="nowrap">
                  <Text size="sm" fw={500} truncate>{entry.username}</Text>
                  <Text size="sm" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
                    {entry.count} {unit}{entry.count !== 1 ? 's' : ''}
                  </Text>
                </Group>
                <Progress
                  value={max ? (entry.count / max) * 100 : 0}
                  color={BAR_COLORS[i % BAR_COLORS.length]}
                  size="sm"
                  radius="xl"
                />
              </Box>
            </Group>
          ))}
        </Stack>
      )}
    </div>
  )
}

interface AlbumHighlightProps {
  label: string
  icon: React.ReactNode
  color: string
  album: RecapAlbumCard | null
}

function AlbumHighlight({ label, icon, color, album }: AlbumHighlightProps) {
  return (
    <Card withBorder radius="md" padding="md">
      <Group gap="xs" mb="sm">
        <ThemeIcon variant="light" color={color} size="sm" radius="xl">{icon}</ThemeIcon>
        <Text size="sm" fw={600} c={color}>{label}</Text>
      </Group>
      {album === null ? (
        <Text size="sm" c="dimmed">No reviewed albums this week.</Text>
      ) : (
        <Group gap="sm" wrap="nowrap" align="flex-start">
          <Image
            src={album.cover_url ?? undefined}
            w={56}
            h={56}
            radius="sm"
            fallbackSrc="https://placehold.co/56x56?text=?"
            alt={album.title}
          />
          <Box style={{ flex: 1, minWidth: 0 }}>
            <Anchor component={Link} to={`/albums/${album.album_id}`} underline="hover" c="inherit">
              <Text size="sm" fw={600} truncate>{album.title}</Text>
            </Anchor>
            {album.artist && <Text size="xs" c="dimmed" truncate>{album.artist}</Text>}
            <Group gap="xs" mt={6}>
              <Badge size="sm" variant="light" color={color}>
                ★ {album.avg_rating.toFixed(1)}
              </Badge>
              <Text size="xs" c="dimmed">
                {album.review_count} review{album.review_count !== 1 ? 's' : ''}
              </Text>
            </Group>
          </Box>
        </Group>
      )}
    </Card>
  )
}

function GuessAccuracyPanel({ accuracy }: { accuracy: GuessAccuracy }) {
  return (
    <div>
      <Title order={6} mb="xs">Guessing Game</Title>
      {accuracy.total_guesses === 0 ? (
        <Text size="sm" c="dimmed">No guesses submitted this week.</Text>
      ) : (
        <Group align="flex-end" gap="xl" wrap="wrap">
          <Box>
            <Text fw={700} style={{ fontSize: 40, lineHeight: 1 }}>
              {accuracy.pct.toFixed(0)}%
            </Text>
            <Text size="xs" c="dimmed">
              {accuracy.correct_guesses} of {accuracy.total_guesses} guesses correct
            </Text>
          </Box>
          {accuracy.per_member.length > 0 && (
            <Stack gap={4} style={{ flex: 1, minWidth: 200 }}>
              {accuracy.per_member.map((m) => (
                <Group key={m.username} justify="space-between" gap="xs" wrap="nowrap">
                  <Text size="sm" truncate>{m.username}</Text>
                  <Text size="sm" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
                    {m.pct.toFixed(0)}% ({m.correct}/{m.total})
                  </Text>
                </Group>
              ))}
            </Stack>
          )}
        </Group>
      )}
    </div>
  )
}

function RecapBody({ recap }: { recap: RecapResponse }) {
  const { data } = recap
  return (
    <Stack gap="lg">
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="lg">
        <Leaderboard title="Albums Added" entries={data.albums_added} unit="album" />
        <Leaderboard title="Albums Reviewed" entries={data.albums_reviewed} unit="review" />
      </SimpleGrid>
      <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="lg">
        <AlbumHighlight
          label="Favorite of the Week"
          icon={<IconTrophy size={14} />}
          color="yellow"
          album={data.favorite_album}
        />
        <AlbumHighlight
          label="Least Favorite"
          icon={<IconMoodSad size={14} />}
          color="gray"
          album={data.least_favorite_album}
        />
      </SimpleGrid>
      <GuessAccuracyPanel accuracy={data.guess_accuracy} />
    </Stack>
  )
}

interface Props {
  groupId: number
}

export default function WeeklyRecap({ groupId }: Props) {
  const { data: recaps, isLoading } = useGroupRecaps(groupId)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  // Default to the most recent recap once loaded.
  useEffect(() => {
    if (recaps && recaps.length > 0 && selectedId === null) {
      setSelectedId(String(recaps[0].id))
    }
  }, [recaps, selectedId])

  const selected = useMemo(
    () => recaps?.find((r) => String(r.id) === selectedId) ?? null,
    [recaps, selectedId],
  )

  if (isLoading) return <Skeleton h={280} radius="md" />

  if (!recaps || recaps.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        No weekly recaps yet — the first one is generated at the end of the week.
      </Text>
    )
  }

  return (
    <Stack gap="md">
      <Group justify="flex-end" align="center" gap="xs" wrap="wrap">
        <Text size="sm" c="dimmed">Week</Text>
        <Select
          aria-label="Select week"
          data={recaps.map((r) => ({
            value: String(r.id),
            label: formatWeekRange(r.week_start, r.week_end),
          }))}
          value={selectedId}
          onChange={setSelectedId}
          allowDeselect={false}
          w={200}
          size="sm"
        />
      </Group>
      {selected && <RecapBody recap={selected} />}
    </Stack>
  )
}
