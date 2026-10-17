import { Text } from '@mantine/core'
import type { MantineSize } from '@mantine/core'
import RichText from './RichText'

interface Props {
  comment: string | null | undefined
  size?: MantineSize
  /** Text shown when there is no comment; omit to render nothing instead. */
  emptyLabel?: string
}

/**
 * A review's comment, set off as a quote.
 *
 * Upright text with a left rule rather than the old quoted-italic style: inside
 * italic text, a reviewer's own `*italic*` would be invisible.
 */
export default function ReviewComment({ comment, size = 'sm', emptyLabel }: Props) {
  if (!comment) {
    return emptyLabel ? <Text size={size} c="dimmed">{emptyLabel}</Text> : null
  }

  return (
    <Text
      size={size}
      style={{
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        borderLeft: '2px solid var(--mantine-color-dark-4)',
        paddingLeft: 'var(--mantine-spacing-xs)',
      }}
    >
      <RichText text={comment} />
    </Text>
  )
}
