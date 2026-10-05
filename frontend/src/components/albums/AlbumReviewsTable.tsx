import { useMemo, useState } from 'react'
import {
  Group,
  ScrollArea,
  Skeleton,
  Stack,
  Table,
  Text,
  UnstyledButton,
} from '@mantine/core'
import {
  IconChevronDown,
  IconChevronRight,
  IconChevronUp,
  IconSelector,
} from '@tabler/icons-react'
import { ratingColor } from '../../utils/ratingColor'
import { SPOILER_COLOR, SpoilerBlur, SpoilerToggle } from './ReviewSpoiler'
import type { AlbumReviewItem } from '../../types/album'

type SortField = 'username' | 'date' | 'rating'
type SortDir = 'asc' | 'desc'

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function sortReviews(items: AlbumReviewItem[], field: SortField, dir: SortDir): AlbumReviewItem[] {
  return [...items].sort((a, b) => {
    let av: string | number = ''
    let bv: string | number = ''
    switch (field) {
      case 'username': av = a.username;   bv = b.username;   break
      case 'date':     av = a.reviewed_at; bv = b.reviewed_at; break
      case 'rating':   av = a.rating ?? 0; bv = b.rating ?? 0; break
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

// ==================== REVIEW ROW ====================

interface ReviewRowProps {
  item: AlbumReviewItem
  isExpanded: boolean
  /** Reviewer and rating blurred, notes sealed shut — see ReviewSpoiler. */
  locked: boolean
  onToggle: () => void
}

function ReviewRow({ item, isExpanded, locked, onToggle }: ReviewRowProps) {
  return (
    <>
      <Table.Tr
        style={{ cursor: locked ? 'default' : 'pointer' }}
        onClick={locked ? undefined : onToggle}
      >
        <Table.Td>
          <SpoilerBlur hidden={locked} strength={5} label="Reviewer hidden">
            <Text size="sm" fw={500}>{item.username}</Text>
          </SpoilerBlur>
        </Table.Td>
        <Table.Td>
          <Text size="sm" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
            {formatDate(item.reviewed_at)}
          </Text>
        </Table.Td>
        <Table.Td>
          <SpoilerBlur hidden={locked} strength={6} label="Rating hidden">
            <Text size="sm" fw={700} c={locked ? SPOILER_COLOR : ratingColor(item.rating)}>
              {item.rating ?? '—'}
            </Text>
          </SpoilerBlur>
        </Table.Td>
        <Table.Td>
          {!locked && (isExpanded ? <IconChevronDown size={14} /> : <IconChevronRight size={14} />)}
        </Table.Td>
      </Table.Tr>

      {/* Never rendered while locked, so the notes are not sitting in the DOM
          one blur away from being read. */}
      {!locked && isExpanded && (
        <Table.Tr>
          <Table.Td
            colSpan={4}
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

// ==================== TABLE ====================

interface Props {
  reviews: AlbumReviewItem[]
  loading: boolean
  /** Whether reviewers and ratings are blurred and notes cannot be expanded. */
  hidden: boolean
  /** Omitted when the viewer has nothing to reveal — no toggle is rendered. */
  onToggleHidden?: () => void
}

/**
 * Every published review of an album, sortable, with notes behind a row click.
 *
 * While its spoiler guard is up only the dates stay legible: the reviewer, the
 * number and the notes are all withheld, so the table says how many people got
 * there first and nothing more. Sorting by reviewer or by rating goes with
 * them, since the row order would otherwise rank the blurs — alphabetically or
 * by score — for anyone who asked it to. The guard is independent of the one
 * over the global score: this is the bigger spoiler of the two, and revealing
 * the aggregate does not reveal this.
 */
export default function AlbumReviewsTable({ reviews, loading, hidden, onToggleHidden }: Props) {
  const [sortField, setSortField] = useState<SortField>('date')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [expandedId, setExpandedId] = useState<number | null>(null)

  // Date is the only column still worth ranking by once the rest is blurred.
  const effectiveField: SortField = hidden && sortField !== 'date' ? 'date' : sortField

  const sortedReviews = useMemo(
    () => sortReviews(reviews, effectiveField, sortDir),
    [reviews, effectiveField, sortDir],
  )

  const toggleSort = (field: SortField) => {
    if (sortField === field) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else { setSortField(field); setSortDir('asc') }
  }

  return (
    <Stack gap="sm">
      <Group justify="space-between" align="center" gap="xs">
        <Text fw={600} size="sm">
          {loading ? (
            <Skeleton h={16} w={80} display="inline-block" />
          ) : (
            `${reviews.length} review${reviews.length !== 1 ? 's' : ''}`
          )}
        </Text>
        {onToggleHidden && (
          <Group gap="xs" align="center" wrap="nowrap">
            {hidden && (
              <Text size="xs" c="dimmed">Hidden until you post your review.</Text>
            )}
            <SpoilerToggle hidden={hidden} onToggle={onToggleHidden} subject="reviews" />
          </Group>
        )}
      </Group>

      {loading ? (
        <Stack gap="xs">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} h={48} radius="sm" />
          ))}
        </Stack>
      ) : !reviews.length ? (
        <Text c="dimmed" size="sm">No reviews yet.</Text>
      ) : (
        <ScrollArea>
          <Table highlightOnHover verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>
                  {hidden ? (
                    <Text size="xs" c="dimmed">Reviewer</Text>
                  ) : (
                    <SortButton field="username" label="Reviewer" active={effectiveField} dir={sortDir} onClick={toggleSort} />
                  )}
                </Table.Th>
                <Table.Th>
                  <SortButton field="date" label="Date" active={effectiveField} dir={sortDir} onClick={toggleSort} />
                </Table.Th>
                <Table.Th>
                  {hidden ? (
                    <Text size="xs" c="dimmed">Rating</Text>
                  ) : (
                    <SortButton field="rating" label="Rating" active={effectiveField} dir={sortDir} onClick={toggleSort} />
                  )}
                </Table.Th>
                <Table.Th w={28} />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {sortedReviews.map((item) => (
                <ReviewRow
                  key={item.id}
                  item={item}
                  isExpanded={expandedId === item.id}
                  locked={hidden}
                  onToggle={() =>
                    setExpandedId((prev) => (prev === item.id ? null : item.id))
                  }
                />
              ))}
            </Table.Tbody>
          </Table>
        </ScrollArea>
      )}
    </Stack>
  )
}
