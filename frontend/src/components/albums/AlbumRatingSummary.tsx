import { Box, Center, Group, Paper, Skeleton, Stack, Text } from '@mantine/core'
import { IconEyeOff } from '@tabler/icons-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ratingColor, ratingColorHex } from '../../utils/ratingColor'
import { SPOILER_COLOR, SPOILER_HINT, SpoilerBlur, SpoilerToggle } from './ReviewSpoiler'
import type { AlbumStatsResponse } from '../../types/album'

/**
 * Shared by the chart and the placeholder that stands in for it, in px rather
 * than through Mantine's `h` prop: `h` resolves to a rem-scaled calc(), while
 * Recharts takes a raw number, and the two only agree at the default root font
 * size. Matching px keeps the swap from nudging the card either way.
 */
const HISTOGRAM_HEIGHT = 100

interface Props {
  stats: AlbumStatsResponse | undefined
  loading: boolean
  /** Whether the global score and histogram are behind their spoiler guard. */
  hidden: boolean
  /** Omitted when the viewer has nothing to reveal — no toggle is rendered. */
  onToggleHidden?: () => void
}

/**
 * Global rating, spread and histogram for an album.
 *
 * Its spoiler guard is its own — lifting the aggregate here says nothing about
 * who thought what, which is why the reviews table keeps a separate one.
 *
 * The score itself blurs, but the histogram comes out of the page entirely: a
 * blur smears a numeral into illegibility, while a bar chart's meaning is
 * carried by where the bars stand and how tall they are, and neither survives
 * being blurred any less readably. Flattening them to one neutral color was not
 * enough either — a grey smear leaning right is still a well-liked album. A
 * placeholder of the same height stands in, so lifting the guard does not
 * reflow the card.
 *
 * The review count stays readable in every state: knowing that eight people
 * have weighed in is not a spoiler, and it is what tells a viewer there is
 * something behind the guard worth coming back for.
 */
export default function AlbumRatingSummary({ stats, loading, hidden, onToggleHidden }: Props) {
  const reviewCount = stats?.review_count ?? 0

  return (
    <Paper withBorder p="md" radius="md">
      {loading ? (
        <Skeleton h={140} />
      ) : (
        <Stack gap="sm">
          {onToggleHidden && (
            <Group justify="flex-end" align="center" wrap="nowrap" gap="xs">
              {hidden && (
                <Text size="xs" c="dimmed" style={{ flex: 1 }}>{SPOILER_HINT}</Text>
              )}
              <SpoilerToggle hidden={hidden} onToggle={onToggleHidden} subject="global score" />
            </Group>
          )}

          <Group gap="xl" align="flex-end">
            <Stack gap={2}>
              <Text size="xs" c="dimmed" tt="uppercase" fw={600} style={{ letterSpacing: 1 }}>
                Global Rating
              </Text>
              <SpoilerBlur hidden={hidden} strength={14} label="Global rating hidden">
                <Text
                  size="xl"
                  fw={700}
                  style={{ fontSize: 40, lineHeight: 1 }}
                  c={hidden ? SPOILER_COLOR : ratingColor(stats?.average_rating)}
                >
                  {stats?.average_rating !== null && stats?.average_rating !== undefined
                    ? stats.average_rating.toFixed(1)
                    : '—'}
                </Text>
              </SpoilerBlur>
              {stats?.rating_stddev != null && reviewCount >= 2 && (
                <SpoilerBlur hidden={hidden} strength={5}>
                  <Text size="xs" c="dimmed">
                    ± {stats.rating_stddev.toFixed(1)} (1σ)
                  </Text>
                </SpoilerBlur>
              )}
              <Text size="xs" c="dimmed">
                {reviewCount} review{reviewCount !== 1 ? 's' : ''}
              </Text>
            </Stack>

            <Box style={{ flex: 1, minWidth: 0 }}>
              {hidden ? (
                <Center
                  style={(theme) => ({
                    height: HISTOGRAM_HEIGHT,
                    border: `1px dashed ${theme.colors.dark[4]}`,
                    borderRadius: theme.radius.sm,
                  })}
                >
                  <Group gap={6} align="center">
                    <IconEyeOff size={14} color="var(--mantine-color-dimmed)" />
                    <Text size="xs" c="dimmed">Rating distribution hidden</Text>
                  </Group>
                </Center>
              ) : (
                <ResponsiveContainer width="100%" height={HISTOGRAM_HEIGHT}>
                  <BarChart data={stats?.histogram ?? []} barCategoryGap="10%" margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--mantine-color-dark-4)" vertical={false} />
                    <XAxis
                      dataKey="bucket_start"
                      tick={{ fontSize: 10, fill: 'var(--mantine-color-dimmed)' }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fontSize: 10, fill: 'var(--mantine-color-dimmed)' }}
                      axisLine={false}
                      tickLine={false}
                      width={20}
                    />
                    <RechartsTooltip
                      formatter={(value, _, props) => [
                        `${value} review${value !== 1 ? 's' : ''}`,
                        `${props.payload.bucket_start}–${props.payload.bucket_end}`,
                      ]}
                      contentStyle={{
                        background: 'var(--mantine-color-dark-7)',
                        border: '1px solid var(--mantine-color-dark-4)',
                        borderRadius: 4,
                        fontSize: 12,
                      }}
                      labelStyle={{ display: 'none' }}
                      itemStyle={{ color: '#c1c2c5' }}
                      cursor={{ fill: 'var(--mantine-color-dark-5)' }}
                    />
                    <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                      {(stats?.histogram ?? []).map((bucket) => (
                        <Cell
                          key={bucket.bucket_start}
                          fill={ratingColorHex(bucket.bucket_start)}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Box>
          </Group>
        </Stack>
      )}
    </Paper>
  )
}
