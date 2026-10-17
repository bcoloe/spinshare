import { useMemo, useState } from 'react'
import {
  ActionIcon,
  Popover,
  ScrollArea,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Tooltip,
  UnstyledButton,
} from '@mantine/core'
import { IconMoodSmile } from '@tabler/icons-react'
import { EMOJI_GROUPS, searchEmoji } from '../../utils/emoji'
import type { EmojiEntry } from '../../utils/emoji'

const COLUMNS = 8
const MAX_SEARCH_RESULTS = 40

interface Props {
  onSelect: (char: string) => void
  disabled?: boolean
}

/**
 * Browse-and-click emoji entry, for when you don't already know the shortcode.
 *
 * Complements rather than replaces `:shortcode:` typing — both insert the same
 * plain Unicode character, so a message reads identically whichever way it was
 * composed, and neither leaves markup behind for the renderer to interpret.
 */
export default function EmojiPicker({ onSelect, disabled }: Props) {
  const [opened, setOpened] = useState(false)
  const [query, setQuery] = useState('')

  const results = useMemo(
    () => (query.trim() ? searchEmoji(query.trim(), MAX_SEARCH_RESULTS) : null),
    [query],
  )

  const choose = (entry: EmojiEntry) => {
    onSelect(entry.char)
    setOpened(false)
    setQuery('')
  }

  const cell = (entry: EmojiEntry) => (
    <Tooltip key={entry.slug} label={`:${entry.slug}:`} openDelay={400} withinPortal>
      <UnstyledButton
        aria-label={entry.slug}
        // mousedown, not click — click blurs the textarea first, and the caret
        // position it loses is exactly where the emoji needs to land.
        onMouseDown={(e) => {
          e.preventDefault()
          choose(entry)
        }}
        style={{
          fontSize: 20,
          lineHeight: 1.2,
          textAlign: 'center',
          borderRadius: 'var(--mantine-radius-sm)',
          padding: 2,
        }}
      >
        {entry.char}
      </UnstyledButton>
    </Tooltip>
  )

  return (
    <Popover
      opened={opened}
      onChange={setOpened}
      onClose={() => setQuery('')}
      position="top-end"
      shadow="md"
      width={300}
      withinPortal
      trapFocus={false}
    >
      <Popover.Target>
        <Tooltip label="Insert emoji">
          <ActionIcon
            size="lg"
            radius="xl"
            variant="subtle"
            color="gray"
            aria-label="Insert emoji"
            disabled={disabled}
            onClick={() => setOpened((o) => !o)}
          >
            <IconMoodSmile size={18} />
          </ActionIcon>
        </Tooltip>
      </Popover.Target>

      <Popover.Dropdown p="xs">
        <Stack gap="xs">
          <TextInput
            size="xs"
            placeholder="Search emoji"
            value={query}
            onChange={(e) => setQuery(e.currentTarget.value)}
            aria-label="Search emoji"
          />

          <ScrollArea h={210} type="auto">
            {results ? (
              results.length === 0 ? (
                <Text size="xs" c="dimmed" ta="center" py="md">
                  No emoji matching &ldquo;{query.trim()}&rdquo;
                </Text>
              ) : (
                <SimpleGrid cols={COLUMNS} spacing={2}>
                  {results.map(cell)}
                </SimpleGrid>
              )
            ) : (
              <Stack gap="xs">
                {EMOJI_GROUPS.map((group) => (
                  <div key={group.name}>
                    <Text size="xs" fw={600} c="dimmed" tt="uppercase" mb={4}>
                      {group.name}
                    </Text>
                    <SimpleGrid cols={COLUMNS} spacing={2}>
                      {group.emoji.map(cell)}
                    </SimpleGrid>
                  </div>
                ))}
              </Stack>
            )}
          </ScrollArea>
        </Stack>
      </Popover.Dropdown>
    </Popover>
  )
}
