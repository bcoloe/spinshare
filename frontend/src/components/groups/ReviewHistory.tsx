import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ActionIcon,
  Button,
  Collapse,
  Group,
  Image,
  Paper,
  Skeleton,
  Slider,
  Stack,
  Table,
  Text,
  TextInput,
  Textarea,
  UnstyledButton,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useQueries } from '@tanstack/react-query'
import {
  IconChevronDown,
  IconChevronRight,
  IconChevronUp,
  IconPencil,
  IconSelector,
} from '@tabler/icons-react'
import { albumService } from '../../services/albumService'
import { useUpdateReview } from '../../hooks/useDailySpin'
import { ApiError } from '../../services/apiClient'
import ReviewAndGuessForm from '../spin/ReviewAndGuessForm'
import type { AlbumReviewItem, GroupAlbumResponse, ReviewResponse } from '../../types/album'
import type { GroupMemberResponse } from '../../types/group'

// ==================== TYPES ====================

type SortField = 'title' | 'artist' | 'date' | 'nominator'
type SortDir = 'asc' | 'desc'

// ==================== HELPERS ====================

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function getNominator(ga: GroupAlbumResponse, members: GroupMemberResponse[]): string {
  return members.find((m) => m.user_id === ga.added_by)?.username ?? '—'
}

function ratingColor(rating: number): string {
  if (rating < 3) return 'red.7'
  if (rating < 5) return '#6b4226'
  if (rating < 7) return 'orange.5'
  if (rating < 9) return 'lime.5'
  return 'green.7'
}

function ratingBg(rating: number): string {
  if (rating < 3) return 'color-mix(in srgb, var(--mantine-color-red-7) 12%, transparent)'
  if (rating < 5) return 'color-mix(in srgb, #6b4226 12%, transparent)'
  if (rating < 7) return 'color-mix(in srgb, var(--mantine-color-orange-5) 12%, transparent)'
  if (rating < 9) return 'color-mix(in srgb, var(--mantine-color-lime-5) 12%, transparent)'
  return 'color-mix(in srgb, var(--mantine-color-green-7) 12%, transparent)'
}

function sortAlbums(
  albums: GroupAlbumResponse[],
  members: GroupMemberResponse[],
  field: SortField,
  dir: SortDir,
): GroupAlbumResponse[] {
  return [...albums].sort((a, b) => {
    let av = '',
      bv = ''
    switch (field) {
      case 'title':
        av = a.album.title
        bv = b.album.title
        break
      case 'artist':
        av = a.album.artist
        bv = b.album.artist
        break
      case 'date':
        av = a.selected_date ?? ''
        bv = b.selected_date ?? ''
        break
      case 'nominator':
        av = getNominator(a, members)
        bv = getNominator(b, members)
        break
    }
    return dir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
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
  const Icon =
    active !== field ? IconSelector : dir === 'asc' ? IconChevronUp : IconChevronDown
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
    <Image src={src} w={36} h={36} radius="sm" style={{ flexShrink: 0 }} />
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

// ==================== UNREVIEWED ROW ====================

interface UnreviewedRowProps {
  ga: GroupAlbumResponse
  groupId: number
  members: GroupMemberResponse[]
  isExpanded: boolean
  onToggle: () => void
  allowGuessing?: boolean
  hasDraft?: boolean
}

function UnreviewedRow({ ga, groupId, members: _members, isExpanded, onToggle, allowGuessing = true, hasDraft = false }: UnreviewedRowProps) {
  const { album } = ga
  const navigate = useNavigate()
  const actionColor = isExpanded ? 'dimmed' : hasDraft ? 'teal' : 'violet'
  const actionLabel = isExpanded ? 'Collapse' : hasDraft ? 'Continue' : 'Review Now'

  return (
    <>
      <Table.Tr style={{ cursor: 'pointer' }} onClick={onToggle}>
        <Table.Td>
          <CoverCell src={album.cover_url} />
        </Table.Td>
        <Table.Td>
          <Text
            size="sm"
            fw={500}
            lineClamp={1}
            style={{ cursor: 'pointer' }}
            onClick={(e) => { e.stopPropagation(); navigate(`/albums/${ga.album_id}`) }}
            onMouseEnter={(e) => { e.currentTarget.style.textDecoration = 'underline' }}
            onMouseLeave={(e) => { e.currentTarget.style.textDecoration = 'none' }}
          >
            {album.title}
          </Text>
        </Table.Td>
        <Table.Td>
          <Text size="sm" c="dimmed" lineClamp={1}>
            {album.artist}
          </Text>
        </Table.Td>
        <Table.Td>
          <Text size="sm" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
            {formatDate(ga.selected_date)}
          </Text>
        </Table.Td>
        <Table.Td>
          <Group gap={4} justify="flex-end">
            {isExpanded
              ? <IconChevronUp size={14} />
              : <IconPencil size={14} color={`var(--mantine-color-${hasDraft ? 'teal' : 'violet'}-6)`} />
            }
            <Text size="xs" c={actionColor}>
              {actionLabel}
            </Text>
          </Group>
        </Table.Td>
      </Table.Tr>

      {isExpanded && (
        <Table.Tr>
          <Table.Td
            colSpan={5}
            style={{ background: 'var(--mantine-color-dark-7)', padding: '16px 20px' }}
          >
            <ReviewAndGuessForm
              albumId={album.id}
              groupId={groupId}
              groupAlbumId={ga.id}
              addedBy={ga.added_by}
              allowGuessing={allowGuessing}
            />
          </Table.Td>
        </Table.Tr>
      )}
    </>
  )
}

// ==================== REVIEWED ROW ====================

interface ReviewedRowProps {
  ga: GroupAlbumResponse
  review: ReviewResponse
  allReviews: AlbumReviewItem[]
  members: GroupMemberResponse[]
  isExpanded: boolean
  onToggle: () => void
}

function ReviewedRow({ ga, review, allReviews, members, isExpanded, onToggle }: ReviewedRowProps) {
  const { album } = ga
  const navigate = useNavigate()
  const [editMode, setEditMode] = useState(false)
  const [editRating, setEditRating] = useState<number>(review.rating ?? 0)
  const [editComment, setEditComment] = useState(review.comment ?? '')
  const [expandedCards, setExpandedCards] = useState<Set<number>>(new Set())
  const updateReview = useUpdateReview(ga.album_id)

  const toggleCard = (id: number) =>
    setExpandedCards((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const memberIds = useMemo(() => new Set(members.map((m) => m.user_id)), [members])
  const memberReviews = useMemo(() => allReviews.filter((r) => memberIds.has(r.user_id)), [allReviews, memberIds])

  const groupAvg = useMemo(() => {
    const rated = memberReviews.filter((r) => r.rating !== null)
    if (rated.length === 0) return null
    const sum = rated.reduce((s, r) => s + r.rating!, 0)
    return Math.round((sum / rated.length) * 10) / 10
  }, [memberReviews])

  const displayReviews = memberReviews.length > 0 ? memberReviews : [review]

  const handleEditOpen = (e: React.MouseEvent) => {
    e.stopPropagation()
    setEditRating(review.rating ?? 0)
    setEditComment(review.comment ?? '')
    setEditMode(true)
    if (!isExpanded) onToggle()
  }

  const handleSave = async () => {
    try {
      await updateReview.mutateAsync({
        reviewId: review.id,
        data: { rating: editRating, comment: editComment || undefined },
      })
      setEditMode(false)
      notifications.show({ color: 'green', message: 'Review updated' })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not update review'
      notifications.show({ color: 'red', message })
    }
  }

  return (
    <>
      <Table.Tr style={{ cursor: 'pointer' }} onClick={onToggle}>
        <Table.Td>
          <CoverCell src={album.cover_url} />
        </Table.Td>
        <Table.Td>
          <Text
            size="sm"
            fw={500}
            lineClamp={1}
            style={{ cursor: 'pointer' }}
            onClick={(e) => { e.stopPropagation(); navigate(`/albums/${ga.album_id}`) }}
            onMouseEnter={(e) => { e.currentTarget.style.textDecoration = 'underline' }}
            onMouseLeave={(e) => { e.currentTarget.style.textDecoration = 'none' }}
          >
            {album.title}
          </Text>
        </Table.Td>
        <Table.Td>
          <Text size="sm" c="dimmed" lineClamp={1}>{album.artist}</Text>
        </Table.Td>
        <Table.Td>
          <Text size="sm" c="dimmed" style={{ whiteSpace: 'nowrap' }}>{formatDate(ga.selected_date)}</Text>
        </Table.Td>
        <Table.Td>
          <Text size="sm" fw={700} c={ratingColor(review.rating ?? 0)}>{review.rating}</Text>
        </Table.Td>
        <Table.Td>
          <Text size="sm" c={groupAvg !== null ? ratingColor(groupAvg) : 'dimmed'} fw={groupAvg !== null ? 600 : undefined}>
            {groupAvg !== null ? groupAvg : '—'}
          </Text>
        </Table.Td>
        <Table.Td>
          <Text size="sm" c="dimmed">{getNominator(ga, members)}</Text>
        </Table.Td>
        <Table.Td>
          <Group gap={6} justify="flex-end" wrap="nowrap">
            <ActionIcon size="sm" variant="subtle" onClick={handleEditOpen}>
              <IconPencil size={13} />
            </ActionIcon>
            {isExpanded ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />}
          </Group>
        </Table.Td>
      </Table.Tr>

      {isExpanded && (
        <Table.Tr>
          <Table.Td
            colSpan={8}
            style={{ background: 'var(--mantine-color-dark-7)', padding: '16px 20px' }}
          >
            <Stack gap="sm">
              {displayReviews.map((r) => {
                const username = ('username' in r ? (r as AlbumReviewItem).username : members.find((m) => m.user_id === r.user_id)?.username) ?? 'Unknown'
                const fullName = ('first_name' in r ? [(r as AlbumReviewItem).first_name, (r as AlbumReviewItem).last_name].filter(Boolean).join(' ') : '')
                const memberName = fullName ? `${fullName} (${username})` : username
                const isMine = r.user_id === review.user_id
                const isCardExpanded = expandedCards.has(r.id) || (isMine && editMode)
                const previewLine = r.comment?.split('\n')[0]

                return (
                  <Paper key={r.id} withBorder p="sm" style={{ background: ratingBg(r.rating ?? 0) }}>
                    <Group
                      justify="space-between"
                      wrap="nowrap"
                      mb={isCardExpanded || previewLine ? 6 : 0}
                      style={{ cursor: 'pointer' }}
                      onClick={(e) => {
                        e.stopPropagation()
                        if (!(isMine && editMode)) toggleCard(r.id)
                      }}
                    >
                      <Group gap={4}>
                        <Text size="sm" fw={600}>{memberName}</Text>
                        {isMine && <Text size="xs" c="dimmed">(you)</Text>}
                      </Group>
                      <Group gap={4} wrap="nowrap">
                        <Text size="sm" fw={700} c={ratingColor(r.rating ?? 0)}>{r.rating}</Text>
                        {isMine && !editMode && (
                          <ActionIcon
                            size="xs"
                            variant="subtle"
                            onClick={(e) => {
                              e.stopPropagation()
                              setEditRating(r.rating ?? 0)
                              setEditComment(r.comment ?? '')
                              setEditMode(true)
                            }}
                          >
                            <IconPencil size={11} />
                          </ActionIcon>
                        )}
                        {!(isMine && editMode) && (
                          isCardExpanded
                            ? <IconChevronUp size={13} />
                            : <IconChevronDown size={13} />
                        )}
                      </Group>
                    </Group>

                    {!isCardExpanded && previewLine && (
                      <Text size="xs" c="dimmed" fs="italic" lineClamp={1}>
                        {previewLine}
                      </Text>
                    )}

                    {isCardExpanded && (
                      isMine && editMode ? (
                        <Stack gap="sm">
                          <div>
                            <Group justify="space-between" mb={4}>
                              <Text size="xs">Rating</Text>
                              <Text size="xs" fw={500} c={ratingColor(editRating)}>{editRating} / 10</Text>
                            </Group>
                            <Slider
                              min={0} max={10} step={0.1}
                              value={editRating} onChange={setEditRating}
                              marks={[0, 2, 4, 6, 8, 10].map((v) => ({ value: v, label: String(v) }))}
                              mb="lg"
                            />
                          </div>
                          <Textarea
                            label="Comment (optional)"
                            value={editComment}
                            onChange={(e) => setEditComment(e.currentTarget.value)}
                            maxLength={1000}
                            autosize
                            minRows={2}
                            size="xs"
                          />
                          <Group gap="xs">
                            <Button size="xs" loading={updateReview.isPending} onClick={handleSave}>Save</Button>
                            <Button size="xs" variant="default" onClick={() => setEditMode(false)}>Cancel</Button>
                          </Group>
                        </Stack>
                      ) : (
                        <Text size="sm" c={r.comment ? undefined : 'dimmed'} fs={r.comment ? 'italic' : undefined} style={{ whiteSpace: 'pre-wrap' }}>
                          {r.comment ? `"${r.comment}"` : 'No notes left.'}
                        </Text>
                      )
                    )}
                  </Paper>
                )
              })}
            </Stack>
          </Table.Td>
        </Table.Tr>
      )}
    </>
  )
}

// ==================== MAIN COMPONENT ====================

interface Props {
  groupId: number
  albums: GroupAlbumResponse[]
  members: GroupMemberResponse[]
  isLoading: boolean
  allowGuessing?: boolean
}

export default function ReviewHistory({ groupId, albums, members, isLoading, allowGuessing = true }: Props) {
  const [pendingOpen, { toggle: togglePending }] = useDisclosure(true)
  const [inProgressOpen, { toggle: toggleInProgress }] = useDisclosure(true)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [expandedInProgressId, setExpandedInProgressId] = useState<number | null>(null)
  const [expandedReviewedId, setExpandedReviewedId] = useState<number | null>(null)

  const [unreviewedField, setUnreviewedField] = useState<SortField>('date')
  const [unreviewedDir, setUnreviewedDir] = useState<SortDir>('desc')
  const [reviewedField, setReviewedField] = useState<SortField>('date')
  const [reviewedDir, setReviewedDir] = useState<SortDir>('desc')
  const [reviewedFilter, setReviewedFilter] = useState('')

  const toggleUnreviewedSort = (f: SortField) => {
    if (unreviewedField === f) setUnreviewedDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else { setUnreviewedField(f); setUnreviewedDir('asc') }
  }
  const toggleReviewedSort = (f: SortField) => {
    if (reviewedField === f) setReviewedDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else { setReviewedField(f); setReviewedDir('asc') }
  }

  const reviewQueries = useQueries({
    queries: albums.map((ga) => ({
      queryKey: ['reviews', ga.album_id, 'me'],
      queryFn: () => albumService.getMyReview(ga.album_id),
      enabled: !!ga.album_id,
    })),
  })

  const allReviewQueries = useQueries({
    queries: albums.map((ga) => ({
      queryKey: ['reviews', ga.album_id, 'all', groupId],
      queryFn: () => albumService.getAllReviews(ga.album_id, groupId),
      enabled: !!ga.album_id,
    })),
  })

  const reviewsLoading =
    reviewQueries.some((q) => q.isLoading) || allReviewQueries.some((q) => q.isLoading)

  const reviewMap = useMemo(() => {
    const map = new Map<number, ReviewResponse | null>()
    albums.forEach((ga, i) => {
      map.set(ga.album_id, reviewQueries[i]?.data ?? null)
    })
    return map
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [albums, reviewQueries])

  const allReviewsMap = useMemo(() => {
    const map = new Map<number, AlbumReviewItem[]>()
    albums.forEach((ga, i) => {
      map.set(ga.album_id, allReviewQueries[i]?.data ?? [])
    })
    return map
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [albums, allReviewQueries])

  const pending = useMemo(
    () => albums.filter((ga) => !reviewMap.get(ga.album_id)),
    [albums, reviewMap],
  )
  const inProgress = useMemo(
    () => albums.filter((ga) => reviewMap.get(ga.album_id)?.is_draft),
    [albums, reviewMap],
  )
  const reviewed = useMemo(
    () => albums.filter((ga) => {
      const review = reviewMap.get(ga.album_id)
      return review && !review.is_draft
    }),
    [albums, reviewMap],
  )

  const sortedPending = useMemo(
    () => sortAlbums(pending, members, unreviewedField, unreviewedDir),
    [pending, members, unreviewedField, unreviewedDir],
  )
  const sortedInProgress = useMemo(
    () => sortAlbums(inProgress, members, unreviewedField, unreviewedDir),
    [inProgress, members, unreviewedField, unreviewedDir],
  )
  const filteredReviewed = useMemo(() => {
    const q = reviewedFilter.toLowerCase()
    if (!q) return reviewed
    return reviewed.filter(
      (ga) =>
        ga.album.title.toLowerCase().includes(q) ||
        ga.album.artist.toLowerCase().includes(q),
    )
  }, [reviewed, reviewedFilter])

  const sortedReviewed = useMemo(
    () => sortAlbums(filteredReviewed, members, reviewedField, reviewedDir),
    [filteredReviewed, members, reviewedField, reviewedDir],
  )

  const toggleExpand = (id: number) => setExpandedId((prev) => (prev === id ? null : id))
  const toggleInProgressExpand = (id: number) => setExpandedInProgressId((prev) => (prev === id ? null : id))

  if (isLoading || reviewsLoading) {
    return (
      <Stack gap="xs">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} h={52} radius="sm" />
        ))}
      </Stack>
    )
  }

  if (!albums.length) {
    return <Text c="dimmed" size="sm">No albums have been spun yet.</Text>
  }

  const unreviewedTable = (rows: GroupAlbumResponse[], expandedRowId: number | null, onToggle: (id: number) => void, hasDraft: boolean) => (
    <Table highlightOnHover verticalSpacing="sm">
      <Table.Thead>
        <Table.Tr>
          <Table.Th w={52} />
          <Table.Th>
            <SortButton field="title" label="Album" active={unreviewedField} dir={unreviewedDir} onClick={toggleUnreviewedSort} />
          </Table.Th>
          <Table.Th>
            <SortButton field="artist" label="Artist" active={unreviewedField} dir={unreviewedDir} onClick={toggleUnreviewedSort} />
          </Table.Th>
          <Table.Th>
            <SortButton field="date" label="Date" active={unreviewedField} dir={unreviewedDir} onClick={toggleUnreviewedSort} />
          </Table.Th>
          <Table.Th />
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {rows.map((ga) => (
          <UnreviewedRow
            key={ga.id}
            ga={ga}
            groupId={groupId}
            members={members}
            isExpanded={expandedRowId === ga.id}
            onToggle={() => onToggle(ga.id)}
            allowGuessing={allowGuessing}
            hasDraft={hasDraft}
          />
        ))}
      </Table.Tbody>
    </Table>
  )

  return (
    <Stack gap="xl">
      {inProgress.length > 0 && (
        <Stack gap="xs">
          <UnstyledButton onClick={toggleInProgress}>
            <Group gap="xs">
              {inProgressOpen ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />}
              <Text fw={600} size="sm" c="teal">
                In Progress ({inProgress.length})
              </Text>
            </Group>
          </UnstyledButton>
          <Collapse in={inProgressOpen}>
            {unreviewedTable(sortedInProgress, expandedInProgressId, toggleInProgressExpand, true)}
          </Collapse>
        </Stack>
      )}

      {pending.length > 0 && (
        <Stack gap="xs">
          <UnstyledButton onClick={togglePending}>
            <Group gap="xs">
              {pendingOpen ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />}
              <Text fw={600} size="sm">
                Pending Reviews ({pending.length})
              </Text>
            </Group>
          </UnstyledButton>
          <Collapse in={pendingOpen}>
            {unreviewedTable(sortedPending, expandedId, toggleExpand, false)}
          </Collapse>
        </Stack>
      )}

      {reviewed.length > 0 && (
        <Stack gap="xs">
          <Group justify="space-between" align="center">
            <Text fw={600} size="sm">Review History</Text>
            <TextInput
              placeholder="Filter by album or artist..."
              size="xs"
              value={reviewedFilter}
              onChange={(e) => setReviewedFilter(e.currentTarget.value)}
              w={220}
            />
          </Group>
          <Table highlightOnHover verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th w={52} />
                <Table.Th>
                  <SortButton field="title" label="Album" active={reviewedField} dir={reviewedDir} onClick={toggleReviewedSort} />
                </Table.Th>
                <Table.Th>
                  <SortButton field="artist" label="Artist" active={reviewedField} dir={reviewedDir} onClick={toggleReviewedSort} />
                </Table.Th>
                <Table.Th>
                  <SortButton field="date" label="Date" active={reviewedField} dir={reviewedDir} onClick={toggleReviewedSort} />
                </Table.Th>
                <Table.Th>Rating</Table.Th>
                <Table.Th>Group Avg</Table.Th>
                <Table.Th>
                  <SortButton field="nominator" label="Nominated By" active={reviewedField} dir={reviewedDir} onClick={toggleReviewedSort} />
                </Table.Th>
                <Table.Th w={56} />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {sortedReviewed.map((ga) => (
                <ReviewedRow
                  key={ga.id}
                  ga={ga}
                  review={reviewMap.get(ga.album_id)!}
                  allReviews={allReviewsMap.get(ga.album_id) ?? []}
                  members={members}
                  isExpanded={expandedReviewedId === ga.id}
                  onToggle={() => setExpandedReviewedId((prev) => (prev === ga.id ? null : ga.id))}
                />
              ))}
            </Table.Tbody>
          </Table>
        </Stack>
      )}
    </Stack>
  )
}
