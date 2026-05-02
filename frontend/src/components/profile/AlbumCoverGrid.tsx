import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
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

function ratingColor(rating: number): string {
  if (rating < 3) return '#fa5252'
  if (rating < 5) return '#6b4226'
  if (rating < 7) return '#fd7e14'
  if (rating < 9) return '#a9e34b'
  return '#40c057'
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
        outline: selected ? `2px solid ${ratingColor(item.rating)}` : 'none',
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
              background: ratingColor(item.rating),
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

export default function AlbumCoverGrid({ items, isLoading, emptyMessage }: Props) {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const navigate = useNavigate()

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

  const selected = selectedIndex !== null ? items[selectedIndex] : null

  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 3, sm: 4, md: 5 }}>
        {items.map((item, i) => (
          <AlbumCell
            key={i}
            item={item}
            selected={selectedIndex === i}
            onClick={() => setSelectedIndex(selectedIndex === i ? null : i)}
          />
        ))}
      </SimpleGrid>

      {selected && (
        <Paper withBorder p="md" radius="md">
          <Group gap="md" align="flex-start">
            {selected.cover_url && (
              <Image
                src={selected.cover_url}
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
                onClick={() => navigate(`/albums/${selected.album_id}`)}
                onMouseEnter={(e) => { e.currentTarget.style.textDecoration = 'underline' }}
                onMouseLeave={(e) => { e.currentTarget.style.textDecoration = 'none' }}
              >
                {selected.title}
              </Text>
              <Text size="sm" c="dimmed">{selected.artist}</Text>
              <Text size="xs" c="dimmed">{releaseYear(selected.release_date)}</Text>
            </Stack>
            <div style={{ marginLeft: 'auto' }}>
              <div
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: '50%',
                  background: ratingColor(selected.rating),
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <span style={{ color: '#fff', fontWeight: 700, fontSize: 14 }}>
                  {selected.rating}
                </span>
              </div>
            </div>
          </Group>
        </Paper>
      )}
    </Stack>
  )
}
