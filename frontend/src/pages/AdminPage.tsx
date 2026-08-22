import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Alert,
  Anchor,
  Badge,
  Button,
  Center,
  Group,
  Paper,
  SegmentedControl,
  SimpleGrid,
  Skeleton,
  Stack,
  Table,
  Tabs,
  Text,
  Title,
  Tooltip,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import {
  IconArrowNarrowRight,
  IconChartBar,
  IconDisc,
  IconExternalLink,
  IconFlag,
  IconStar,
  IconUsers,
  IconUsersGroup,
} from '@tabler/icons-react'
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import AppShell from '../components/layout/AppShell'
import EditLinksModal from '../components/albums/EditLinksModal'
import StatCard from '../components/explore/StatCard'
import {
  useAdminMetrics,
  useDismissLinkReport,
  useLinkReports,
  useResolveLinkReport,
} from '../hooks/useAdmin'
import { useSiteStats } from '../hooks/useExplore'
import { ApiError } from '../services/apiClient'
import {
  LINK_FIELD_TO_COLUMN,
  LINK_LABELS,
  REASON_LABELS,
  type AdminLinkReportItem,
  type LinkReportStatus,
  type ReportableLink,
} from '../types/linkReport'
import type { LinkColumn } from '../components/albums/EditLinksModal'
import { albumLinkUrl } from '../utils/albumLinkUrl'

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const mins = Math.round(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}

export default function AdminPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  // Driven by the query string so a notification can deep-link to a tab.
  const tab = searchParams.get('tab') ?? 'reports'
  const status = (searchParams.get('status') ?? 'open') as LinkReportStatus
  const [reviewing, setReviewing] = useState<AdminLinkReportItem | null>(null)

  const { data: reports = [], isLoading } = useLinkReports(status, tab === 'reports')

  const setTab = (next: string | null) => {
    searchParams.set('tab', next ?? 'reports')
    setSearchParams(searchParams, { replace: true })
  }
  const resolveReport = useResolveLinkReport()
  const dismissReport = useDismissLinkReport()

  const setStatus = (next: string) => {
    searchParams.set('status', next)
    setSearchParams(searchParams, { replace: true })
  }

  const handleDismiss = async (report: AdminLinkReportItem) => {
    try {
      await dismissReport.mutateAsync({ reportId: report.id, note: null })
      notifications.show({ color: 'gray', message: 'Report dismissed' })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not dismiss report'
      notifications.show({ color: 'red', message })
    }
  }

  const handleMarkResolved = async (report: AdminLinkReportItem) => {
    try {
      await resolveReport.mutateAsync(report.id)
      notifications.show({ color: 'green', message: 'Report resolved' })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not resolve report'
      notifications.show({ color: 'red', message })
    }
  }

  // Saving the edit is what settles the report, so resolve is chained off the
  // modal's success rather than fired when the admin opens it.
  const handleSavedFromReview = async () => {
    if (!reviewing) return
    try {
      await resolveReport.mutateAsync(reviewing.id)
      notifications.show({ color: 'green', message: 'Link updated and report resolved' })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Link saved, but the report is still open'
      notifications.show({ color: 'yellow', message })
    } finally {
      setReviewing(null)
    }
  }

  return (
    <AppShell>
      {reviewing && (
        <EditLinksModal
          opened
          onClose={() => setReviewing(null)}
          album={reviewing.album}
          initialOverrides={
            reviewing.suggested_value
              ? {
                  [LINK_FIELD_TO_COLUMN[reviewing.link_field] as LinkColumn]:
                    reviewing.suggested_value,
                }
              : undefined
          }
          highlightField={LINK_FIELD_TO_COLUMN[reviewing.link_field] as LinkColumn}
          highlightNote={
            reviewing.suggested_value
              ? `Suggested by ${reviewing.reporter_username ?? 'a deleted user'}`
              : 'Reported as bad — no replacement suggested'
          }
          onSaved={handleSavedFromReview}
        />
      )}

      <Stack gap="lg">
        <Title order={2}>Admin</Title>

        <Tabs value={tab} onChange={setTab}>
          <Tabs.List>
            <Tabs.Tab value="reports" leftSection={<IconFlag size={14} />}>
              Link reports
            </Tabs.Tab>
            <Tabs.Tab value="metrics" leftSection={<IconChartBar size={14} />}>
              Site metrics
            </Tabs.Tab>
          </Tabs.List>
        </Tabs>

        {tab === 'metrics' ? (
          <MetricsTab />
        ) : (
        <Stack gap="lg">
        <Group justify="space-between" align="center">
          <Text size="sm" c="dimmed">
            Link corrections reported by members. Reviewing one opens the album's link
            editor prefilled with the suggestion.
          </Text>
          <SegmentedControl
            value={status}
            onChange={setStatus}
            data={[
              { label: 'Open', value: 'open' },
              { label: 'Resolved', value: 'resolved' },
              { label: 'Dismissed', value: 'dismissed' },
            ]}
          />
        </Group>

        {isLoading ? (
          <Stack gap="xs">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} h={48} radius="sm" />
            ))}
          </Stack>
        ) : reports.length === 0 ? (
          <Alert icon={<IconFlag size={16} />} color="gray">
            {status === 'open'
              ? 'No open link reports. Nothing to review right now.'
              : `No ${status} link reports.`}
          </Alert>
        ) : (
          <Table.ScrollContainer minWidth={800}>
            <Table striped highlightOnHover verticalSpacing="sm">
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Album</Table.Th>
                  <Table.Th>Reported link</Table.Th>
                  <Table.Th>Suggested replacement</Table.Th>
                  <Table.Th>Reason</Table.Th>
                  <Table.Th>Reporter</Table.Th>
                  <Table.Th />
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {reports.map((r) => (
                  <Table.Tr key={r.id}>
                    <Table.Td>
                      <Anchor component={Link} to={`/albums/${r.album_id}`} size="sm">
                        {r.album.title}
                      </Anchor>
                      <Text size="xs" c="dimmed">
                        {r.album.artist}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Badge color="orange" variant="light">
                        {LINK_LABELS[r.link_field]}
                      </Badge>
                      <PreviewLink
                        link={r.link_field}
                        value={r.current_value}
                        label="Preview the link being reported"
                        emptyText="empty"
                      />
                    </Table.Td>
                    <Table.Td maw={220}>
                      {/* Arrow ties this back to the reported value in the
                          previous column, so the row reads as old -> new. */}
                      <Group gap={4} wrap="nowrap" align="flex-start">
                        <IconArrowNarrowRight
                          size={14}
                          style={{ flexShrink: 0, marginTop: 6, opacity: 0.45 }}
                        />
                        {/* Prefer the raw URL the reporter pasted — it is exactly
                            what they were looking at when they filed the report. */}
                        <PreviewLink
                          link={r.link_field}
                          value={r.suggested_url ?? r.suggested_value}
                          display={r.suggested_value ?? r.suggested_url}
                          label="Preview the suggested replacement"
                          emptyText="none"
                          color="violet"
                        />
                      </Group>
                    </Table.Td>
                    <Table.Td maw={280}>
                      <Badge
                        size="sm"
                        variant="light"
                        color={r.reason_code === 'missing' ? 'blue' : 'gray'}
                      >
                        {REASON_LABELS[r.reason_code]}
                      </Badge>
                      {r.reason_detail && (
                        <Text size="xs" c="dimmed" lineClamp={3} mt={4}>
                          {r.reason_detail}
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{r.reporter_username ?? '[deleted]'}</Text>
                      <Text size="xs" c="dimmed">
                        {relativeTime(r.created_at)}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      {r.status === 'open' ? (
                        <Group gap="xs" wrap="nowrap">
                          <Button size="xs" onClick={() => setReviewing(r)}>
                            Review
                          </Button>
                          <Button
                            size="xs"
                            variant="subtle"
                            color="gray"
                            onClick={() => handleDismiss(r)}
                            loading={dismissReport.isPending}
                          >
                            Dismiss
                          </Button>
                          <Button
                            size="xs"
                            variant="subtle"
                            color="gray"
                            onClick={() => handleMarkResolved(r)}
                          >
                            Mark fixed
                          </Button>
                        </Group>
                      ) : (
                        <Center>
                          <Text size="xs" c="dimmed">
                            {r.resolution_note ?? r.status}
                          </Text>
                        </Center>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        )}
        </Stack>
        )}
      </Stack>
    </AppShell>
  )
}

/**
 * A link value rendered as a clickable preview, so an admin can open the thing
 * being judged rather than eyeballing a bare service ID.
 */
function PreviewLink({
  link,
  value,
  display,
  label,
  emptyText,
  color,
}: {
  link: ReportableLink
  value: string | null
  display?: string | null
  label: string
  emptyText: string
  color?: string
}) {
  const href = albumLinkUrl(link, value)

  if (!href) {
    return (
      <Text size="xs" c="dimmed" mt={4}>
        {display ?? value ?? emptyText}
      </Text>
    )
  }

  return (
    <Tooltip label={label}>
      <Anchor
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        size="xs"
        c={color}
        lineClamp={2}
        mt={4}
        display="inline-flex"
        style={{ alignItems: 'center', gap: 4 }}
      >
        {display ?? value}
        <IconExternalLink size={11} style={{ flexShrink: 0 }} />
      </Anchor>
    </Tooltip>
  )
}

function MetricsTab() {
  const { data: metrics, isLoading } = useAdminMetrics()
  const { data: siteStats } = useSiteStats()

  if (isLoading || !metrics) {
    return (
      <SimpleGrid cols={{ base: 2, sm: 4 }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} h={88} radius="sm" />
        ))}
      </SimpleGrid>
    )
  }

  const window = `in ${metrics.window_days}d`

  return (
    <Stack gap="lg">
      <SimpleGrid cols={{ base: 2, sm: 4 }}>
        <StatCard
          label="Members"
          value={metrics.users.total}
          icon={<IconUsers size={20} />}
          delta={`+${metrics.users.recent} ${window}`}
        />
        <StatCard
          label="Groups"
          value={metrics.groups.total}
          icon={<IconUsersGroup size={20} />}
          delta={`+${metrics.groups.recent} ${window}`}
        />
        <StatCard
          label="Albums"
          value={metrics.albums.total}
          icon={<IconDisc size={20} />}
          delta={`+${metrics.albums.recent} ${window}`}
        />
        <StatCard
          label="Reviews"
          value={metrics.reviews.total}
          icon={<IconStar size={20} />}
          delta={`+${metrics.reviews.recent} ${window}`}
        />
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <DaySeriesChart title="Signups" data={metrics.signups_by_day} color="var(--mantine-color-violet-5)" />
        <DaySeriesChart title="Reviews" data={metrics.reviews_by_day} color="var(--mantine-color-orange-5)" />
      </SimpleGrid>

      {/* Content stats already exist publicly — reused rather than recomputed. */}
      {siteStats && (
        <Group gap="lg">
          <Text size="sm" c="dimmed">
            {siteStats.total_albums_nominated.toLocaleString()} albums nominated ·{' '}
            {siteStats.total_active_groups.toLocaleString()} active groups ·{' '}
            {siteStats.total_active_members.toLocaleString()} active members
          </Text>
          <Anchor component={Link} to="/explore/stats" size="sm">
            Full site stats
          </Anchor>
        </Group>
      )}
    </Stack>
  )
}

function DaySeriesChart({
  title,
  data,
  color,
}: {
  title: string
  data: { day: string; count: number }[]
  color: string
}) {
  return (
    <Paper withBorder p="md">
      <Text size="sm" fw={600} mb="sm">
        {title}
      </Text>
      {data.length === 0 ? (
        <Text size="xs" c="dimmed">
          No activity in this window.
        </Text>
      ) : (
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={data}>
            <XAxis
              dataKey="day"
              tick={{ fontSize: 10 }}
              tickFormatter={(d: string) => d.slice(5)}
            />
            <YAxis allowDecimals={false} tick={{ fontSize: 10 }} width={24} />
            <RechartsTooltip />
            <Bar dataKey="count" fill={color} radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </Paper>
  )
}
