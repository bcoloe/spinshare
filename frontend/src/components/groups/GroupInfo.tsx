import { useNavigate } from 'react-router-dom'
import { Badge, Button, Divider, Group, SimpleGrid, Skeleton, Stack, Text, Title } from '@mantine/core'
import { IconListDetails } from '@tabler/icons-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import ChartCarousel from '../profile/ChartCarousel'
import MemberList from './MemberList'
import { useGroupStats, useGroupPendingInvitations } from '../../hooks/useGroups'
import type { GroupDetailResponse, GuessHistogramBucket, MemberGuessAccuracyItem } from '../../types/group'

const DECADE_COLORS = [
  '#7950f2', '#228be6', '#12b886', '#f03e3e', '#fd7e14',
  '#fab005', '#74c0fc', '#63e6be', '#ffa8a8', '#e599f7',
]
const OUTSIDE_GROUP_COLOR = '#5c5f66'

const HISTOGRAM_COLORS = [
  '#f03e3e', '#fd7e14', '#fd7e14', '#fab005', '#fab005',
  '#94d82d', '#94d82d', '#40c057', '#40c057', '#2f9e44',
]

interface MemberPieProps {
  data: { username: string; count: number }[]
}

function MemberPieChart({ data }: MemberPieProps) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={data}
          dataKey="count"
          nameKey="username"
          cx="50%"
          cy="50%"
          outerRadius={85}
          label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
          labelLine={false}
        >
          {data.map((entry, i) => (
            <Cell
              key={i}
              fill={entry.username === 'Outside Group' ? OUTSIDE_GROUP_COLOR : DECADE_COLORS[i % DECADE_COLORS.length]}
            />
          ))}
        </Pie>
        <RechartsTooltip
          formatter={(value) => [`${value} album${value !== 1 ? 's' : ''}`, 'Albums']}
          contentStyle={{ background: 'var(--mantine-color-dark-7)', border: '1px solid var(--mantine-color-dark-4)', borderRadius: 4, fontSize: 13 }}
          labelStyle={{ color: '#c1c2c5' }}
          itemStyle={{ color: '#c1c2c5' }}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

interface StatCardProps {
  label: string
  value: string | number
}

function StatCard({ label, value }: StatCardProps) {
  return (
    <Stack
      gap={4}
      p="md"
      style={{ border: '1px solid var(--mantine-color-dark-4)', borderRadius: 8 }}
    >
      <Text size="xl" fw={700}>{value}</Text>
      <Text size="xs" c="dimmed">{label}</Text>
    </Stack>
  )
}

interface GuessHistogramChartProps {
  data: GuessHistogramBucket[]
}

function GuessHistogramChart({ data }: GuessHistogramChartProps) {
  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={data} barCategoryGap="15%">
        <CartesianGrid strokeDasharray="3 3" stroke="var(--mantine-color-dark-4)" vertical={false} />
        <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'var(--mantine-color-dimmed)' }} axisLine={false} tickLine={false} interval={0} />
        <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: 'var(--mantine-color-dimmed)' }} axisLine={false} tickLine={false} width={24} />
        <RechartsTooltip
          formatter={(value) => [`${value} album${value !== 1 ? 's' : ''}`, 'Albums']}
          contentStyle={{ background: 'var(--mantine-color-dark-7)', border: '1px solid var(--mantine-color-dark-4)', borderRadius: 4, fontSize: 13 }}
          labelStyle={{ color: '#c1c2c5' }}
          itemStyle={{ color: '#c1c2c5' }}
          cursor={{ fill: 'var(--mantine-color-dark-5)' }}
        />
        <Bar dataKey="count" radius={[4, 4, 0, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={HISTOGRAM_COLORS[i % HISTOGRAM_COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

interface MemberGuessAccuracyChartProps {
  data: MemberGuessAccuracyItem[]
}

function MemberGuessAccuracyChart({ data }: MemberGuessAccuracyChartProps) {
  const chartData = [...data]
    .sort((a, b) => b.accuracy - a.accuracy)
    .map((d) => ({
      username: d.username,
      pct: Math.round(d.accuracy * 100),
      correct: d.correct_guesses,
      total: d.total_guesses,
    }))
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, chartData.length * 40)}>
      <BarChart data={chartData} layout="vertical" barCategoryGap="25%">
        <CartesianGrid strokeDasharray="3 3" stroke="var(--mantine-color-dark-4)" horizontal={false} />
        <XAxis
          type="number"
          domain={[0, 100]}
          tickFormatter={(v) => `${v}%`}
          tick={{ fontSize: 11, fill: 'var(--mantine-color-dimmed)' }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="username"
          width={90}
          tick={{ fontSize: 12, fill: 'var(--mantine-color-dimmed)' }}
          axisLine={false}
          tickLine={false}
        />
        <RechartsTooltip
          formatter={(value, _name, props) =>
            [`${value}% (${props.payload.correct} / ${props.payload.total} correct)`, 'Accuracy']
          }
          contentStyle={{ background: 'var(--mantine-color-dark-7)', border: '1px solid var(--mantine-color-dark-4)', borderRadius: 4, fontSize: 13 }}
          labelStyle={{ color: '#c1c2c5' }}
          itemStyle={{ color: '#c1c2c5' }}
          cursor={{ fill: 'var(--mantine-color-dark-5)' }}
        />
        <Bar dataKey="pct" radius={[0, 4, 4, 0]} fill="#7950f2" />
      </BarChart>
    </ResponsiveContainer>
  )
}

interface Props {
  group: GroupDetailResponse
}

export default function GroupInfo({ group }: Props) {
  const navigate = useNavigate()
  const { data: stats, isLoading: statsLoading } = useGroupStats(group.id)

  const canManage =
    group.current_user_role === 'owner' || group.current_user_role === 'admin'

  const { data: pendingInvitations = [] } = useGroupPendingInvitations(group.id, canManage)

  const canManageCatalog = canManage

  return (
    <Stack gap="xl">
      <div>
        <Title order={5} mb="sm">Group Stats</Title>
        {statsLoading ? (
          <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="md">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} h={80} radius="md" />)}
          </SimpleGrid>
        ) : (
          <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="md">
            <StatCard label="Members" value={stats?.member_count ?? group.member_count} />
            <StatCard label="Albums Added" value={stats?.albums_added ?? '—'} />
            <StatCard label="Albums Reviewed" value={stats?.albums_reviewed ?? '—'} />
            <StatCard
              label="Formed"
              value={stats?.formed_at ? formatDate(stats.formed_at) : '—'}
            />
          </SimpleGrid>
        )}
      </div>

      <Divider />

      <div>
        <Title order={5} mb="sm">Charts</Title>
        <ChartCarousel
          slides={[
            {
              title: 'Nominations per Member',
              loading: statsLoading,
              empty: !stats?.albums_per_member.length,
              emptyMessage: 'No albums added yet.',
              chart: <MemberPieChart data={stats?.albums_per_member ?? []} />,
            },
            {
              title: 'Selected per Member',
              loading: statsLoading,
              empty: !stats?.selected_per_member.length,
              emptyMessage: 'No albums selected yet.',
              chart: <MemberPieChart data={stats?.selected_per_member ?? []} />,
            },
            {
              title: 'Albums by Decade',
              loading: statsLoading,
              empty: !stats?.decade_breakdown.length,
              emptyMessage: 'No albums added yet.',
              chart: (
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={stats?.decade_breakdown} barCategoryGap="30%">
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--mantine-color-dark-4)" vertical={false} />
                    <XAxis dataKey="decade" tick={{ fontSize: 12, fill: 'var(--mantine-color-dimmed)' }} axisLine={false} tickLine={false} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: 'var(--mantine-color-dimmed)' }} axisLine={false} tickLine={false} width={24} />
                    <RechartsTooltip
                      formatter={(value) => [`${value} album${value !== 1 ? 's' : ''}`, 'Albums']}
                      contentStyle={{ background: 'var(--mantine-color-dark-7)', border: '1px solid var(--mantine-color-dark-4)', borderRadius: 4, fontSize: 13 }}
                      labelStyle={{ color: '#c1c2c5' }}
                      itemStyle={{ color: '#c1c2c5' }}
                      cursor={{ fill: 'var(--mantine-color-dark-5)' }}
                    />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                      {(stats?.decade_breakdown ?? []).map((_, i) => (
                        <Cell key={i} fill={DECADE_COLORS[i % DECADE_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ),
            },
            {
              title: 'Guess Accuracy Distribution',
              loading: statsLoading,
              empty: !(stats?.guess_histogram ?? []).some((b) => b.count > 0),
              emptyMessage: 'No guesses submitted yet.',
              chart: <GuessHistogramChart data={stats?.guess_histogram ?? []} />,
            },
            {
              title: 'Member Guess Accuracy',
              loading: statsLoading,
              empty: !(stats?.member_guess_accuracy ?? []).length,
              emptyMessage: 'No guesses submitted yet.',
              chart: <MemberGuessAccuracyChart data={stats?.member_guess_accuracy ?? []} />,
            },
          ]}
        />
      </div>

      <Divider />

      <div>
        <Title order={5} mb="sm">Members</Title>
        <MemberList group={group} />
      </div>

      {canManage && pendingInvitations.length > 0 && (
        <>
          <Divider />
          <div>
            <Group gap="xs" mb="sm">
              <Title order={5}>Pending Invitations</Title>
              <Badge size="sm" variant="light" color="violet">{pendingInvitations.length}</Badge>
            </Group>
            <Stack gap="xs">
              {pendingInvitations.map((inv) => (
                <Group key={inv.id} justify="space-between">
                  <Text size="sm">{inv.invited_email}</Text>
                  <Text size="xs" c="dimmed">
                    invited by {inv.inviter_username} · expires{' '}
                    {new Date(inv.expires_at).toLocaleDateString()}
                  </Text>
                </Group>
              ))}
            </Stack>
          </div>
        </>
      )}

      {canManageCatalog && (
        <>
          <Divider />
          <div>
            <Title order={5} mb="sm">Catalog</Title>
            <Text size="sm" c="dimmed" mb="sm">
              Manage nominations, review pending albums, and update statuses.
            </Text>
            <Button
              variant="light"
              leftSection={<IconListDetails size={16} />}
              onClick={() => navigate(`/groups/${group.id}/catalog`)}
            >
              Open catalog
            </Button>
          </div>
        </>
      )}
    </Stack>
  )
}
