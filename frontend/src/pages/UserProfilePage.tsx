import { useEffect, useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import {
  Box,
  Divider,
  Group,
  Paper,
  ScrollArea,
  SegmentedControl,
  SimpleGrid,
  Skeleton,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  UnstyledButton,
} from '@mantine/core'
import {
  IconChevronDown,
  IconChevronRight,
  IconChevronUp,
  IconSelector,
} from '@tabler/icons-react'
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
import AppShell from '../components/layout/AppShell'
import AlbumCoverGrid from '../components/profile/AlbumCoverGrid'
import { useUserNominationBreakdown, useUserProfile, useUserReviews } from '../hooks/useUserProfile'
import type { UserReviewItem } from '../types/auth'

// ==================== TYPES ====================

type Tab = 'stats' | 'favorites' | 'least-favorites' | 'history'
type SortField = 'title' | 'artist' | 'date' | 'rating'
type SortDir = 'asc' | 'desc'

// ==================== HELPERS ====================

const DECADE_COLORS = [
  '#7950f2', '#228be6', '#12b886', '#f03e3e', '#fd7e14',
  '#fab005', '#74c0fc', '#63e6be', '#ffa8a8', '#e599f7',
]

function ratingColor(rating: number): string {
  if (rating < 3) return 'red.7'
  if (rating < 5) return '#6b4226'
  if (rating < 7) return 'orange.5'
  if (rating < 9) return 'lime.5'
  return 'green.7'
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function sortReviews(
  items: UserReviewItem[],
  field: SortField,
  dir: SortDir,
): UserReviewItem[] {
  return [...items].sort((a, b) => {
    let av: string | number = ''
    let bv: string | number = ''
    switch (field) {
      case 'title':   av = a.title;      bv = b.title;      break
      case 'artist':  av = a.artist;     bv = b.artist;     break
      case 'date':    av = a.reviewed_at; bv = b.reviewed_at; break
      case 'rating':  av = a.rating;     bv = b.rating;     break
    }
    if (typeof av === 'number' && typeof bv === 'number') {
      return dir === 'asc' ? av - bv : bv - av
    }
    return dir === 'asc'
      ? String(av).localeCompare(String(bv))
      : String(bv).localeCompare(String(av))
  })
}

// ==================== SORT BUTTON ====================

interface SortButtonProps {
  field: SortField
  label: string
  active: SortField
  dir: SortDir
  onClick: (f: SortField) => void
}

function SortButton({ field, label, active, dir, onClick }: SortButtonProps) {
  const Icon = active !== field ? IconSelector : dir === 'asc' ? IconChevronUp : IconChevronDown
  return (
    <UnstyledButton
      onClick={() => onClick(field)}
      style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}
      c="dimmed"
    >
      {label}
      <Icon size={13} />
    </UnstyledButton>
  )
}

// ==================== COVER CELL ====================

function CoverCell({ src }: { src: string | null }) {
  return src ? (
    <img src={src} width={36} height={36} style={{ borderRadius: 4, flexShrink: 0, objectFit: 'cover' }} />
  ) : (
    <div
      style={{
        width: 36,
        height: 36,
        background: 'var(--mantine-color-dark-5)',
        borderRadius: 4,
        flexShrink: 0,
      }}
    />
  )
}

// ==================== HISTORY ROW ====================

interface HistoryRowProps {
  item: UserReviewItem
  isExpanded: boolean
  onToggle: () => void
}

function HistoryRow({ item, isExpanded, onToggle }: HistoryRowProps) {
  return (
    <>
      <Table.Tr style={{ cursor: 'pointer' }} onClick={onToggle}>
        <Table.Td>
          <CoverCell src={item.cover_url} />
        </Table.Td>
        <Table.Td>
          <Text size="sm" fw={500} lineClamp={1}>{item.title}</Text>
        </Table.Td>
        <Table.Td>
          <Text size="sm" c="dimmed" lineClamp={1}>{item.artist}</Text>
        </Table.Td>
        <Table.Td>
          <Text size="sm" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
            {formatDate(item.reviewed_at)}
          </Text>
        </Table.Td>
        <Table.Td>
          <Text size="sm" fw={700} c={ratingColor(item.rating)}>{item.rating}</Text>
        </Table.Td>
        <Table.Td>
          {isExpanded ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
        </Table.Td>
      </Table.Tr>

      {isExpanded && (
        <Table.Tr>
          <Table.Td
            colSpan={6}
            style={{ background: 'var(--mantine-color-dark-7)', padding: '12px 20px' }}
          >
            <Text
              size="sm"
              c={item.comment ? undefined : 'dimmed'}
              fs={item.comment ? 'italic' : undefined}
              style={{ whiteSpace: 'pre-wrap' }}
            >
              {item.comment ? `"${item.comment}"` : 'No notes left.'}
            </Text>
          </Table.Td>
        </Table.Tr>
      )}
    </>
  )
}

// ==================== STAT CARD ====================

interface StatCardProps {
  label: string
  value: number | string
  loading: boolean
}

function StatCard({ label, value, loading }: StatCardProps) {
  return (
    <Paper withBorder p="md" radius="md">
      {loading ? (
        <Skeleton h={40} />
      ) : (
        <Stack gap={4}>
          <Text size="xl" fw={700}>{value}</Text>
          <Text size="xs" c="dimmed">{label}</Text>
        </Stack>
      )}
    </Paper>
  )
}

// ==================== MAIN PAGE ====================

export default function UserProfilePage() {
  const { username } = useParams<{ username: string }>()
  const [searchParams] = useSearchParams()
  const [tab, setTab] = useState<Tab>((searchParams.get('tab') as Tab) ?? 'stats')

  useEffect(() => {
    const paramTab = searchParams.get('tab') as Tab | null
    if (paramTab) setTab(paramTab)
  }, [searchParams])

  const [sortField, setSortField] = useState<SortField>('date')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [filter, setFilter] = useState('')
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const { data: profile, isLoading: profileLoading } = useUserProfile(username!)
  const { data: reviews = [], isLoading: reviewsLoading } = useUserReviews(username!)
  const { data: breakdown, isLoading: breakdownLoading } = useUserNominationBreakdown(username!)

  const favorites = useMemo(
    () =>
      reviews
        .filter((r) => r.rating >= 9.0)
        .sort((a, b) => b.rating - a.rating),
    [reviews],
  )

  const leastFavorites = useMemo(() => {
    if (!reviews.length) return []
    const sorted = [...reviews].sort((a, b) => a.rating - b.rating)
    const cutoff = Math.max(1, Math.ceil(sorted.length * 0.1))
    const threshold = sorted[cutoff - 1].rating
    return reviews
      .filter((r) => r.rating <= threshold)
      .sort((a, b) => a.rating - b.rating)
  }, [reviews])

  const filteredHistory = useMemo(() => {
    const q = filter.toLowerCase()
    const base = q
      ? reviews.filter(
          (r) =>
            r.title.toLowerCase().includes(q) ||
            r.artist.toLowerCase().includes(q),
        )
      : reviews
    return sortReviews(base, sortField, sortDir)
  }, [reviews, filter, sortField, sortDir])

  const toggleSort = (field: SortField) => {
    if (sortField === field) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else { setSortField(field); setSortDir('asc') }
  }

  return (
    <AppShell>
      <Stack gap="lg">
        {profileLoading ? (
          <Skeleton h={40} w={200} />
        ) : (
          <div>
            <Title order={3}>{profile?.username}</Title>
            <Text size="sm" c="dimmed">
              Member since{' '}
              {profile?.member_since
                ? new Date(profile.member_since).toLocaleDateString(undefined, {
                    year: 'numeric',
                    month: 'long',
                  })
                : '—'}
            </Text>
          </div>
        )}

        <Box
          p={3}
          style={{
            background:
              'linear-gradient(135deg, var(--mantine-color-violet-9) 0%, var(--mantine-color-dark-6) 100%)',
            borderRadius: 'var(--mantine-radius-sm)',
          }}
        >
          <SegmentedControl
            fullWidth
            value={tab}
            onChange={(v) => setTab(v as Tab)}
            data={[
              { label: 'Stats', value: 'stats' },
              { label: 'Favorites', value: 'favorites' },
              { label: 'Least Favorites', value: 'least-favorites' },
              { label: 'History', value: 'history' },
            ]}
            styles={{ root: { background: 'transparent' } }}
          />
        </Box>

        {/* ── STATS TAB ── */}
        {tab === 'stats' && (
          <Stack gap="xl">
            <SimpleGrid cols={{ base: 1, sm: 3 }}>
              <StatCard
                label="Albums Reviewed"
                value={profile?.total_reviews ?? 0}
                loading={profileLoading}
              />
              <StatCard
                label="Groups"
                value={profile?.total_groups ?? 0}
                loading={profileLoading}
              />
              <StatCard
                label="Albums Nominated"
                value={profile?.albums_nominated ?? 0}
                loading={profileLoading}
              />
            </SimpleGrid>

            <Divider />

            <Stack gap="xs">
              <Text fw={600} size="sm">Nominations by Decade</Text>

              {breakdownLoading ? (
                <Skeleton h={220} />
              ) : !breakdown?.decade_breakdown.length ? (
                <Text c="dimmed" size="sm">No nominations yet.</Text>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={breakdown.decade_breakdown} barCategoryGap="30%">
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--mantine-color-dark-4)" vertical={false} />
                    <XAxis
                      dataKey="decade"
                      tick={{ fontSize: 12, fill: 'var(--mantine-color-dimmed)' }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fontSize: 12, fill: 'var(--mantine-color-dimmed)' }}
                      axisLine={false}
                      tickLine={false}
                      width={24}
                    />
                    <RechartsTooltip
                      formatter={(value) => [`${value} album${value !== 1 ? 's' : ''}`, 'Nominations']}
                      contentStyle={{
                        background: 'var(--mantine-color-dark-7)',
                        border: '1px solid var(--mantine-color-dark-4)',
                        borderRadius: 4,
                        fontSize: 13,
                      }}
                      labelStyle={{ color: '#c1c2c5' }}
                      itemStyle={{ color: '#c1c2c5' }}
                      cursor={{ fill: 'var(--mantine-color-dark-5)' }}
                    />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                      {breakdown.decade_breakdown.map((_, i) => (
                        <Cell key={i} fill={DECADE_COLORS[i % DECADE_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Stack>
          </Stack>
        )}

        {/* ── FAVORITES TAB ── */}
        {tab === 'favorites' && (
          <AlbumCoverGrid
            items={favorites}
            isLoading={reviewsLoading}
            emptyMessage="No albums rated 9.0 or above yet."
          />
        )}

        {/* ── LEAST FAVORITES TAB ── */}
        {tab === 'least-favorites' && (
          <AlbumCoverGrid
            items={leastFavorites}
            isLoading={reviewsLoading}
            emptyMessage="Not enough reviews yet."
          />
        )}

        {/* ── HISTORY TAB ── */}
        {tab === 'history' && (
          <Stack gap="sm">
            <Group justify="space-between" align="center">
              <Text fw={600} size="sm">
                {reviews.length} review{reviews.length !== 1 ? 's' : ''}
              </Text>
              <TextInput
                placeholder="Filter by album or artist..."
                size="xs"
                value={filter}
                onChange={(e) => setFilter(e.currentTarget.value)}
                w={220}
              />
            </Group>

            {reviewsLoading ? (
              <Stack gap="xs">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Skeleton key={i} h={52} radius="sm" />
                ))}
              </Stack>
            ) : !reviews.length ? (
              <Text c="dimmed" size="sm">No reviews yet.</Text>
            ) : (
              <ScrollArea>
                <Table highlightOnHover verticalSpacing="sm">
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th w={52} />
                      <Table.Th>
                        <SortButton field="title" label="Album" active={sortField} dir={sortDir} onClick={toggleSort} />
                      </Table.Th>
                      <Table.Th>
                        <SortButton field="artist" label="Artist" active={sortField} dir={sortDir} onClick={toggleSort} />
                      </Table.Th>
                      <Table.Th>
                        <SortButton field="date" label="Date" active={sortField} dir={sortDir} onClick={toggleSort} />
                      </Table.Th>
                      <Table.Th>
                        <SortButton field="rating" label="Rating" active={sortField} dir={sortDir} onClick={toggleSort} />
                      </Table.Th>
                      <Table.Th w={28} />
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {filteredHistory.map((item) => (
                      <HistoryRow
                        key={item.review_id}
                        item={item}
                        isExpanded={expandedId === item.review_id}
                        onToggle={() =>
                          setExpandedId((prev) =>
                            prev === item.review_id ? null : item.review_id,
                          )
                        }
                      />
                    ))}
                  </Table.Tbody>
                </Table>
              </ScrollArea>
            )}
          </Stack>
        )}
      </Stack>
    </AppShell>
  )
}
