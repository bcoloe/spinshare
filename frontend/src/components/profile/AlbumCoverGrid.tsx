import { Fragment, useState } from 'react'
import { ratingColorHex } from '../../utils/ratingColor'
import { useNavigate } from 'react-router-dom'
import { useMediaQuery } from '@mantine/hooks'
import { Group, Image, Paper, SimpleGrid, Skeleton, Stack, Text } from '@mantine/core'

export interface AlbumCoverItem {
  album_id: number
  cover_url: string | null
  title: string
  artist: string
  release_date: string | null
  rating: number
}

interface Props {
  items: AlbumCoverItem[]
  isLoading: boolean
  emptyMessage: string
}


function releaseYear(release_date: string | null): string {
  if (!release_date) return '—'
  return String(release_date).slice(0, 4)
}

interface AlbumCellProps {
  item: AlbumCoverItem
  selected: boolean
  onClick: () => void
}

function AlbumCell({ item, selected, onClick }: AlbumCellProps) {
  const [hovered, setHovered] = useState(false)
  const showOverlay = hovered || selected

  return (
    <div
      style={{
        position: 'relative',
        aspectRatio: '1',
        borderRadius: 4,
        overflow: 'hidden',
        cursor: 'pointer',
        outline: selected ? `2px solid ${ratingColorHex(item.rating)}` : 'none',
        outlineOffset: 2,
      }}
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {item.cover_url ? (
        <Image src={item.cover_url} w="100%" h="100%" style={{ objectFit: 'cover', display: 'block' }} />
      ) : (
        <div style={{ width: '100%', height: '100%', background: 'var(--mantine-color-dark-5)' }} />
      )}

      {showOverlay && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(0,0,0,0.45)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: '50%',
              background: ratingColorHex(item.rating),
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 8px rgba(0,0,0,0.5)',
            }}
          >
            <span style={{ color: '#fff', fontWeight: 700, fontSize: 15, lineHeight: 1 }}>
              {item.rating}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

function AlbumDetail({ item }: { item: AlbumCoverItem }) {
  const navigate = useNavigate()

  return (
    <Paper withBorder p="md" radius="md">
      <Group gap="md" align="flex-start">
        {item.cover_url && (
          <Image
            src={item.cover_url}
            w={64}
            h={64}
            radius="sm"
            style={{ objectFit: 'cover', flexShrink: 0 }}
          />
        )}
        <Stack gap={2}>
          <Text
            fw={600}
            size="sm"
            lineClamp={2}
            style={{ cursor: 'pointer' }}
            onClick={() => navigate(`/albums/${item.album_id}`)}
            onMouseEnter={(e) => { e.currentTarget.style.textDecoration = 'underline' }}
            onMouseLeave={(e) => { e.currentTarget.style.textDecoration = 'none' }}
          >
            {item.title}
          </Text>
          <Text size="sm" c="dimmed">{item.artist}</Text>
          <Text size="xs" c="dimmed">{releaseYear(item.release_date)}</Text>
        </Stack>
        <div style={{ marginLeft: 'auto' }}>
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: '50%',
              background: ratingColorHex(item.rating),
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <span style={{ color: '#fff', fontWeight: 700, fontSize: 14 }}>
              {item.rating}
            </span>
          </div>
        </div>
      </Group>
    </Paper>
  )
}

export default function AlbumCoverGrid({ items, isLoading, emptyMessage }: Props) {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  // Mirror the responsive column counts of the grid below so the detail panel
  // can be inserted directly beneath the selected album's row.
  const isMd = useMediaQuery('(min-width: 62em)')
  const isSm = useMediaQuery('(min-width: 48em)')
  const cols = isMd ? 5 : isSm ? 4 : 3

  if (isLoading) {
    return (
      <SimpleGrid cols={{ base: 3, sm: 4, md: 5 }}>
        {Array.from({ length: 9 }).map((_, i) => (
          <Skeleton key={i} style={{ aspectRatio: '1' }} radius="sm" />
        ))}
      </SimpleGrid>
    )
  }

  if (!items.length) {
    return <Text c="dimmed" size="sm">{emptyMessage}</Text>
  }

  const selectedRow = selectedIndex !== null ? Math.floor(selectedIndex / cols) : null

  const rows: AlbumCoverItem[][] = []
  for (let i = 0; i < items.length; i += cols) {
    rows.push(items.slice(i, i + cols))
  }

  return (
    <Stack gap="md">
      {rows.map((rowItems, rowIdx) => (
        <Fragment key={rowIdx}>
          <SimpleGrid cols={cols}>
            {rowItems.map((item, j) => {
              const idx = rowIdx * cols + j
              return (
                <AlbumCell
                  key={idx}
                  item={item}
                  selected={selectedIndex === idx}
                  onClick={() => setSelectedIndex(selectedIndex === idx ? null : idx)}
                />
              )
            })}
          </SimpleGrid>

          {selectedRow === rowIdx && selectedIndex !== null && (
            <AlbumDetail item={items[selectedIndex]} />
          )}
        </Fragment>
      ))}
    </Stack>
  )
}
