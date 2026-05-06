import { useState } from 'react'
import { ActionIcon, Group, Skeleton, Stack, Text } from '@mantine/core'
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react'

export interface ChartSlide {
  title: string
  loading: boolean
  empty: boolean
  emptyMessage: string
  chart: React.ReactNode
}

interface Props {
  slides: ChartSlide[]
}

export default function ChartCarousel({ slides }: Props) {
  const [index, setIndex] = useState(0)
  const total = slides.length
  const slide = slides[index]

  return (
    <Stack gap="sm">
      <Group justify="space-between" align="center">
        <Text fw={600} size="sm">{slide.title}</Text>
        <Group gap={4} align="center">
          <ActionIcon
            variant="subtle"
            size="sm"
            onClick={() => setIndex((i) => (i - 1 + total) % total)}
            disabled={total <= 1}
            aria-label="Previous chart"
          >
            <IconChevronLeft size={14} />
          </ActionIcon>
          <Text size="xs" c="dimmed" w={32} ta="center">{index + 1} / {total}</Text>
          <ActionIcon
            variant="subtle"
            size="sm"
            onClick={() => setIndex((i) => (i + 1) % total)}
            disabled={total <= 1}
            aria-label="Next chart"
          >
            <IconChevronRight size={14} />
          </ActionIcon>
        </Group>
      </Group>

      {slide.loading ? (
        <Skeleton h={180} />
      ) : slide.empty ? (
        <Text size="sm" c="dimmed">{slide.emptyMessage}</Text>
      ) : (
        slide.chart
      )}
    </Stack>
  )
}
