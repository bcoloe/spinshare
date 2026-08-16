import { Badge, Tooltip } from '@mantine/core'
import { IconCircleFilled } from '@tabler/icons-react'
import { useGroupPresence } from '../../hooks/useChat'

interface Props {
  groupId: number
  /** Renders as a button affordance when the caller wires up onClick. */
  onClick?: () => void
  size?: 'xs' | 'sm'
}

/**
 * "N online" with a live dot.
 *
 * Reads from the shared app socket's presence state — mounting this costs no
 * request and no database query. Shown in the group banner and again in the
 * chat overlay header.
 */
export default function PresenceBadge({ groupId, onClick, size = 'sm' }: Props) {
  const { online } = useGroupPresence(groupId)
  const count = online.length

  const label =
    count > 0
      ? `Online now: ${online.map((m) => m.username).join(', ')}`
      : 'Nobody is online right now'

  return (
    <Tooltip label={label} multiline maw={280}>
      <Badge
        size={size}
        variant="light"
        color={count > 0 ? 'teal' : 'gray'}
        leftSection={<IconCircleFilled size={7} />}
        onClick={onClick}
        style={onClick ? { cursor: 'pointer' } : undefined}
      >
        {count} online
      </Badge>
    </Tooltip>
  )
}
