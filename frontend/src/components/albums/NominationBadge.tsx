import { Badge, Tooltip } from '@mantine/core'
import { IconUsers } from '@tabler/icons-react'

interface Props {
  // Distinct users who have nominated this album across all groups.
  total: number
  // Distinct members nominating within the current group, or null when there is
  // no group context (e.g. the album page or the global/bot groups).
  groupCount?: number | null
  // Hide the group figure behind "??" (chaos-mode groups, where a real count
  // would give away chaos picks and the nomination-guessing game).
  maskGroup?: boolean
}

/**
 * Compact nomination indicator styled after the genre badges (orange).
 * Reads as [TOTAL | GROUP]; the group figure is omitted when not applicable
 * and shown as "??" for chaos-mode groups.
 */
export default function NominationBadge({ total, groupCount = null, maskGroup = false }: Props) {
  const hasGroup = maskGroup || groupCount !== null
  const groupDisplay = maskGroup ? '??' : groupCount
  const people = `${total} ${total === 1 ? 'person' : 'people'}`
  const label = !hasGroup
    ? `Nominated by ${people}`
    : maskGroup
      ? `Nominated by ${people} overall · group nominations hidden in chaos mode`
      : `Nominated by ${people} overall · ${groupCount} in this group`

  return (
    <Tooltip label={label} withArrow>
      <Badge
        size="sm"
        variant="light"
        color="orange"
        leftSection={<IconUsers size={12} />}
        styles={{ label: { display: 'flex', alignItems: 'center', gap: 6 } }}
        style={{ cursor: 'default' }}
      >
        <span>{total}</span>
        {hasGroup && (
          <>
            <span style={{ opacity: 0.45 }}>|</span>
            <span>{groupDisplay}</span>
          </>
        )}
      </Badge>
    </Tooltip>
  )
}
