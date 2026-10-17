import { useState } from 'react'
import { ActionIcon, Group, Popover, Tooltip, UnstyledButton } from '@mantine/core'
import { IconMoodPlus, IconPlus } from '@tabler/icons-react'
import { EmojiGrid } from '../common/EmojiPicker'

/** One tap covers most reactions; "more" opens the full grid. */
export const QUICK_REACTIONS = ['👍', '❤️', '😂', '🔥', '😮', '😢'] as const

interface Props {
  onReact: (emoji: string) => void
  /** Lets the row keep its action bar visible while the picker is open. */
  onOpenChange?: (opened: boolean) => void
}

export default function ReactionPicker({ onReact, onOpenChange }: Props) {
  const [opened, setOpened] = useState(false)
  const [showAll, setShowAll] = useState(false)

  const setOpen = (next: boolean) => {
    setOpened(next)
    if (!next) setShowAll(false)
    onOpenChange?.(next)
  }

  const choose = (emoji: string) => {
    onReact(emoji)
    setOpen(false)
  }

  return (
    <Popover
      opened={opened}
      onChange={setOpen}
      position="top-end"
      shadow="md"
      width={showAll ? 300 : undefined}
      withinPortal
    >
      <Popover.Target>
        <Tooltip label="Add reaction">
          <ActionIcon
            size="sm"
            variant="subtle"
            color="gray"
            aria-label="Add reaction"
            onClick={() => setOpen(!opened)}
          >
            <IconMoodPlus size={13} />
          </ActionIcon>
        </Tooltip>
      </Popover.Target>

      <Popover.Dropdown p="xs">
        {showAll ? (
          <EmojiGrid onSelect={choose} />
        ) : (
          <Group gap={2} wrap="nowrap">
            {QUICK_REACTIONS.map((emoji) => (
              <UnstyledButton
                key={emoji}
                aria-label={`React ${emoji}`}
                onClick={() => choose(emoji)}
                style={{ fontSize: 20, lineHeight: 1.2, padding: 2, borderRadius: 'var(--mantine-radius-sm)' }}
              >
                {emoji}
              </UnstyledButton>
            ))}
            <Tooltip label="More emoji">
              <ActionIcon
                variant="subtle"
                color="gray"
                aria-label="More emoji"
                onClick={() => setShowAll(true)}
              >
                <IconPlus size={14} />
              </ActionIcon>
            </Tooltip>
          </Group>
        )}
      </Popover.Dropdown>
    </Popover>
  )
}
