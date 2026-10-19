import { Group, Tooltip, UnstyledButton } from '@mantine/core'
import type { MessageReaction } from '../../types/message'

interface Props {
  reactions: MessageReaction[]
  currentUserId: number | undefined
  /** Usernames for the "who reacted" tooltip. */
  usernames: Map<number, string>
  onToggle: (emoji: string, remove: boolean) => void
}

/** "🔥 3" chips under a message. Yours are highlighted; clicking one toggles your reaction. */
export default function ReactionChips({ reactions, currentUserId, usernames, onToggle }: Props) {
  if (reactions.length === 0) return null

  return (
    <Group gap={4} mt={4}>
      {reactions.map((r) => {
        const mine = currentUserId !== undefined && r.user_ids.includes(currentUserId)
        const who = r.user_ids.map((id) => usernames.get(id) ?? 'someone').join(', ')
        return (
          <Tooltip key={r.emoji} label={who} multiline maw={240}>
            <UnstyledButton
              aria-label={`${r.emoji} ${r.count}`}
              aria-pressed={mine}
              onClick={() => onToggle(r.emoji, mine)}
              px={6}
              style={{
                fontSize: 'var(--mantine-font-size-xs)',
                lineHeight: '20px',
                borderRadius: 'var(--mantine-radius-xl)',
                border: `1px solid ${mine ? 'var(--mantine-color-violet-5)' : 'var(--mantine-color-dark-4)'}`,
                background: mine ? 'var(--mantine-color-violet-9)' : 'var(--mantine-color-dark-6)',
              }}
            >
              {r.emoji} {r.count}
            </UnstyledButton>
          </Tooltip>
        )
      })}
    </Group>
  )
}
