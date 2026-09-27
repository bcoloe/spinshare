import { Anchor, Stack, Text, Tooltip } from '@mantine/core'
import { Link } from 'react-router-dom'

/** Inline "a, b, and c" list of nominator profile links. */
export function NominatorLinks({ usernames }: { usernames: string[] }) {
  const links = usernames.map((u) => (
    <Anchor key={u} component={Link} to={`/users/${u}`} fw={600} size="sm">
      {u}
    </Anchor>
  ))
  if (links.length === 0) return null
  if (links.length === 1) return <>{links[0]}</>
  if (links.length === 2) return <>{links[0]} and {links[1]}</>
  return <>{links.slice(0, -1).reduce<React.ReactNode[]>((acc, l, i) => [...acc, l, <span key={`sep-${i}`}>, </span>], [])}, and {links[links.length - 1]}</>
}

interface NominatorSummaryProps {
  usernames: string[]
  c?: string
}

/**
 * Compact nominator label for dense rows: the username when there is one nominator,
 * or "Multiple (n)" that reveals the full list on hover, focus, or tap.
 */
export function NominatorSummary({ usernames, c = 'dimmed' }: NominatorSummaryProps) {
  if (usernames.length <= 1) {
    return <Text size="xs" lineClamp={1} c={c}>{usernames[0] ?? '—'}</Text>
  }
  return (
    <Tooltip
      withArrow
      events={{ hover: true, focus: true, touch: true }}
      label={
        <Stack gap={0}>
          {usernames.map((u) => <Text key={u} size="xs">{u}</Text>)}
        </Stack>
      }
    >
      <Text
        size="xs"
        c={c}
        tabIndex={0}
        role="button"
        aria-label={`Nominated by ${usernames.join(', ')}`}
        style={{ textDecoration: 'underline dotted', cursor: 'help', whiteSpace: 'nowrap' }}
        // A tap should reveal the list, not open the row it sits in
        onClick={(e) => e.stopPropagation()}
      >
        Multiple ({usernames.length})
      </Text>
    </Tooltip>
  )
}
