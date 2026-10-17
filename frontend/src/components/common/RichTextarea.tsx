import { useMemo, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import {
  ActionIcon,
  Group,
  Paper,
  Stack,
  Text,
  Textarea,
  Tooltip,
  UnstyledButton,
} from '@mantine/core'
import type { MantineSize } from '@mantine/core'
import { IconBold, IconItalic } from '@tabler/icons-react'
import { replaceShortcodes, searchEmoji } from '../../utils/emoji'
import { toggleFormat } from '../../utils/richText'
import type { FormatMarker } from '../../utils/richText'
import type { GroupMemberResponse } from '../../types/group'
import EmojiPicker from './EmojiPicker'

const MAX_SUGGESTIONS = 6

/** The token before the caret that a chosen suggestion replaces. */
const MENTION_TOKEN = /@[\w.-]*$/
const EMOJI_TOKEN = /:[a-z0-9_+-]*$/i

const IS_MAC = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)
const MOD_KEY = IS_MAC ? '⌘' : 'Ctrl+'

interface Props {
  value: string
  onChange: (value: string) => void
  /**
   * Members offered by `@` autocomplete. Omit to disable mentions entirely —
   * reviews do, since mentioning someone there would point them at a review
   * they may not be allowed to see yet.
   */
  members?: GroupMemberResponse[]
  /** When set, Enter submits and Shift+Enter inserts a newline. */
  onSubmit?: () => void
  /** Rendered after the formatting controls, e.g. a send button. */
  actions?: ReactNode
  label?: string
  placeholder?: string
  maxLength: number
  minRows?: number
  maxRows?: number
  size?: MantineSize
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

/**
 * The text editor shared by chat and review comments.
 *
 * Adds, on top of a plain textarea: `**bold**` / `*italic*` toggles (buttons
 * and Ctrl/Cmd+B / Ctrl/Cmd+I), `:shortcode` emoji autocomplete plus a picker,
 * and — when `members` is given — `@handle` autocomplete. Everything it inserts
 * is plain text (Unicode emoji, markdown-style markers), so what gets stored
 * reads sensibly even where it isn't rendered.
 */
export default function RichTextarea({
  value,
  onChange,
  members,
  onSubmit,
  actions,
  label,
  placeholder,
  maxLength,
  minRows = 2,
  maxRows,
  size,
  disabled,
}: Props) {
  const [caret, setCaret] = useState(0)
  const [highlighted, setHighlighted] = useState(0)
  // Escape hides the suggestion list until the text next changes. A flag rather
  // than a sentinel caret: the keyup that follows Escape re-syncs the caret.
  const [dismissed, setDismissed] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const mentionQuery = members && !dismissed ? activeMentionQuery(value, caret) : null
  const emojiQuery = dismissed ? null : activeEmojiQuery(value, caret)

  const suggestions = useMemo<Suggestion[]>(() => {
    if (members && mentionQuery !== null) {
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
        // The emoji itself goes into the text, not the shortcode — so what
        // gets stored is plain Unicode that reads the same everywhere.
        insert: e.char,
        token: EMOJI_TOKEN,
        icon: e.char,
        label: `:${e.slug}:`,
      }))
    }

    return []
  }, [mentionQuery, emojiQuery, members])

  /** Commit a new value and put the selection back where the edit left it. */
  const commit = (next: string, start: number, end = start) => {
    // A programmatic edit must respect the limit the textarea enforces on typing.
    if (next.length > maxLength) return
    onChange(next)
    setCaret(end)
    setDismissed(false)
    requestAnimationFrame(() => {
      inputRef.current?.focus()
      inputRef.current?.setSelectionRange(start, end)
    })
  }

  /** Drop text in at the caret, leaving what surrounds it alone. */
  const insertAtCaret = (text: string) => {
    const at = Math.min(caret, value.length)
    commit(value.slice(0, at) + text + value.slice(at), at + text.length)
  }

  /**
   * Accept typed or pasted text, turning any completed `:shortcode:` into its
   * emoji on the spot — so every editor stores Unicode, not shortcodes.
   *
   * Only the text before the caret is substituted. Typing and pasting both
   * leave the caret after what they added, and everything after it was already
   * substituted on an earlier change — so this is complete, keeps the caret
   * put, and never sees a fragment cut off from the word it belongs to.
   */
  const handleTyped = (raw: string, rawCaret: number) => {
    const before = replaceShortcodes(raw.slice(0, rawCaret))
    const next = before + raw.slice(rawCaret)
    onChange(next)
    setCaret(before.length)
    setHighlighted(0)
    setDismissed(false)
    if (next !== raw) {
      requestAnimationFrame(() => inputRef.current?.setSelectionRange(before.length, before.length))
    }
  }

  const applySuggestion = (suggestion: Suggestion) => {
    // Replace the partial token the caret is sitting in, leaving whatever
    // follows the caret untouched.
    const before = value.slice(0, caret).replace(suggestion.token, `${suggestion.insert} `)
    commit(before + value.slice(caret), before.length)
  }

  const applyFormat = (marker: FormatMarker) => {
    const el = inputRef.current
    if (!el || disabled) return
    const result = toggleFormat(
      { value, start: el.selectionStart, end: el.selectionEnd },
      marker,
    )
    commit(result.value, result.start, result.end)
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.ctrlKey || event.metaKey) && !event.altKey) {
      const key = event.key.toLowerCase()
      if (key === 'b' || key === 'i') {
        event.preventDefault()
        applyFormat(key === 'b' ? '**' : '*')
        return
      }
    }

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
        setDismissed(true)
        return
      }
    }

    if (onSubmit && event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      onSubmit()
    }
  }

  const syncCaret = () => setCaret(inputRef.current?.selectionStart ?? 0)

  const formatButton = (marker: FormatMarker, name: string, shortcut: string, icon: ReactNode) => (
    <Tooltip label={`${name} (${MOD_KEY}${shortcut})`}>
      <ActionIcon
        size="lg"
        radius="xl"
        variant="subtle"
        color="gray"
        aria-label={name}
        disabled={disabled}
        // mousedown, not click — click blurs the textarea first and loses the
        // selection the marker needs to wrap.
        onMouseDown={(e) => {
          e.preventDefault()
          applyFormat(marker)
        }}
      >
        {icon}
      </ActionIcon>
    </Tooltip>
  )

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

      <Group gap={4} align="flex-end" wrap="nowrap">
        <Textarea
          ref={inputRef}
          flex={1}
          label={label}
          size={size}
          autosize
          minRows={minRows}
          maxRows={maxRows}
          maxLength={maxLength}
          placeholder={placeholder}
          value={value}
          disabled={disabled}
          onChange={(e) => handleTyped(e.currentTarget.value, e.currentTarget.selectionStart ?? 0)}
          onKeyDown={handleKeyDown}
          onKeyUp={syncCaret}
          onClick={syncCaret}
        />
        {formatButton('**', 'Bold', 'B', <IconBold size={16} />)}
        {formatButton('*', 'Italic', 'I', <IconItalic size={16} />)}
        <EmojiPicker onSelect={insertAtCaret} disabled={disabled} />
        {actions}
      </Group>
    </Stack>
  )
}
