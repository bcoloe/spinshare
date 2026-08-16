import { useMemo, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { ActionIcon, Group, Paper, Stack, Text, Textarea, UnstyledButton } from '@mantine/core'
import { IconSend } from '@tabler/icons-react'
import { replaceShortcodes, searchEmoji } from '../../utils/emoji'
import type { GroupMemberResponse } from '../../types/group'

const MAX_MESSAGE_LENGTH = 2000
const MAX_SUGGESTIONS = 6

/** The token before the caret that a chosen suggestion replaces. */
const MENTION_TOKEN = /@[\w.-]*$/
const EMOJI_TOKEN = /:[a-z0-9_+-]*$/i

interface Props {
  members: GroupMemberResponse[]
  onSend: (body: string) => void
  isSending: boolean
  disabled?: boolean
}

/**
 * A completion offer for the partial token the caret is sitting in.
 *
 * Mentions and emoji are normalised into one shape so the keyboard handling,
 * highlight tracking and insertion logic stay single-path — the two triggers
 * differ only in what they search and what they leave behind.
 */
interface Suggestion {
  key: string
  /** Replaces the partial token in the textarea. */
  insert: string
  /** Which token pattern the insert replaces. */
  token: RegExp
  /** Leading glyph in the dropdown (the emoji itself, or nothing). */
  icon?: string
  label: string
}

/** The partial `@handle` immediately before the caret, if we're in one. */
function activeMentionQuery(value: string, caret: number): string | null {
  const upToCaret = value.slice(0, caret)
  // Only match when the '@' starts a word, so an email address never opens the
  // autocomplete.
  const match = upToCaret.match(/(?:^|\s)@([\w.-]*)$/)
  return match ? match[1] : null
}

/** The partial `:shortcode` immediately before the caret, if we're in one. */
function activeEmojiQuery(value: string, caret: number): string | null {
  const upToCaret = value.slice(0, caret)
  // Require the ':' to start a word and be followed by at least two characters.
  // A lone or mid-word colon is far too common in ordinary prose — and in
  // timestamps and URLs — to be worth opening a picker for.
  const match = upToCaret.match(/(?:^|\s):([a-z0-9_+-]{2,})$/i)
  return match ? match[1] : null
}

export default function MessageComposer({ members, onSend, isSending, disabled }: Props) {
  const [value, setValue] = useState('')
  const [caret, setCaret] = useState(0)
  const [highlighted, setHighlighted] = useState(0)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const mentionQuery = activeMentionQuery(value, caret)
  const emojiQuery = activeEmojiQuery(value, caret)

  const suggestions = useMemo<Suggestion[]>(() => {
    if (mentionQuery !== null) {
      const needle = mentionQuery.toLowerCase()
      return members
        .filter((m) => m.username.toLowerCase().startsWith(needle))
        .slice(0, MAX_SUGGESTIONS)
        .map((m) => ({
          key: `mention-${m.user_id}`,
          insert: `@${m.username}`,
          token: MENTION_TOKEN,
          label: `@${m.username}`,
        }))
    }

    if (emojiQuery !== null) {
      return searchEmoji(emojiQuery, MAX_SUGGESTIONS).map((e) => ({
        key: `emoji-${e.slug}`,
        // The emoji itself goes into the message, not the shortcode — so what
        // gets stored is plain Unicode that reads the same everywhere.
        insert: e.char,
        token: EMOJI_TOKEN,
        icon: e.char,
        label: `:${e.slug}:`,
      }))
    }

    return []
  }, [mentionQuery, emojiQuery, members])

  const applySuggestion = (suggestion: Suggestion) => {
    // Replace the partial token the caret is sitting in, leaving whatever
    // follows the caret untouched.
    const before = value.slice(0, caret).replace(suggestion.token, `${suggestion.insert} `)
    const next = before + value.slice(caret)
    setValue(next)
    setCaret(before.length)
    requestAnimationFrame(() => {
      inputRef.current?.focus()
      inputRef.current?.setSelectionRange(before.length, before.length)
    })
  }

  const submit = () => {
    // Substitute over the whole body rather than only what the picker inserted,
    // so shortcodes that were typed out in full or pasted in still resolve.
    const body = replaceShortcodes(value).trim()
    if (!body || isSending || disabled) return
    onSend(body)
    setValue('')
    setCaret(0)
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (suggestions.length > 0) {
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        setHighlighted((i) => (i + 1) % suggestions.length)
        return
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault()
        setHighlighted((i) => (i - 1 + suggestions.length) % suggestions.length)
        return
      }
      if (event.key === 'Tab' || (event.key === 'Enter' && !event.shiftKey)) {
        event.preventDefault()
        applySuggestion(suggestions[highlighted])
        setHighlighted(0)
        return
      }
      if (event.key === 'Escape') {
        event.preventDefault()
        setCaret(-1) // closes the list without altering the text
        return
      }
    }

    // Enter sends, Shift+Enter inserts a newline.
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  const syncCaret = () => setCaret(inputRef.current?.selectionStart ?? 0)

  return (
    <Stack gap={4} style={{ position: 'relative' }}>
      {suggestions.length > 0 && (
        <Paper
          withBorder
          radius="sm"
          shadow="md"
          p={4}
          style={{ position: 'absolute', bottom: '100%', left: 0, right: 0, zIndex: 3 }}
        >
          <Stack gap={0}>
            {suggestions.map((suggestion, i) => (
              <UnstyledButton
                key={suggestion.key}
                onMouseDown={(e) => {
                  // mousedown, not click — click would blur the textarea first
                  // and lose the caret position we need.
                  e.preventDefault()
                  applySuggestion(suggestion)
                }}
                onMouseEnter={() => setHighlighted(i)}
                p="xs"
                style={{
                  borderRadius: 'var(--mantine-radius-sm)',
                  background:
                    i === highlighted ? 'var(--mantine-color-dark-5)' : 'transparent',
                }}
              >
                <Group gap="xs" wrap="nowrap">
                  {suggestion.icon && <Text size="sm">{suggestion.icon}</Text>}
                  <Text size="sm" truncate>
                    {suggestion.label}
                  </Text>
                </Group>
              </UnstyledButton>
            ))}
          </Stack>
        </Paper>
      )}

      <Group gap="xs" align="flex-end" wrap="nowrap">
        <Textarea
          ref={inputRef}
          flex={1}
          autosize
          minRows={1}
          maxRows={5}
          maxLength={MAX_MESSAGE_LENGTH}
          placeholder={
            disabled ? 'Join this group to chat' : 'Message the group — @ to mention, : for emoji'
          }
          value={value}
          disabled={disabled}
          onChange={(e) => {
            setValue(e.currentTarget.value)
            setCaret(e.currentTarget.selectionStart ?? 0)
            setHighlighted(0)
          }}
          onKeyDown={handleKeyDown}
          onKeyUp={syncCaret}
          onClick={syncCaret}
        />
        <ActionIcon
          size="lg"
          radius="xl"
          variant="filled"
          color="violet"
          aria-label="Send message"
          disabled={disabled || !value.trim()}
          loading={isSending}
          onClick={submit}
        >
          <IconSend size={18} />
        </ActionIcon>
      </Group>
    </Stack>
  )
}
