import { useMemo, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { ActionIcon, Group, Paper, Stack, Text, Textarea, UnstyledButton } from '@mantine/core'
import { IconSend } from '@tabler/icons-react'
import type { GroupMemberResponse } from '../../types/group'

const MAX_MESSAGE_LENGTH = 2000
const MAX_SUGGESTIONS = 5

interface Props {
  members: GroupMemberResponse[]
  onSend: (body: string) => void
  isSending: boolean
  disabled?: boolean
}

/** The partial `@handle` immediately before the caret, if we're in one. */
function activeMentionQuery(value: string, caret: number): string | null {
  const upToCaret = value.slice(0, caret)
  // Only match when the '@' starts a word, so an email address never opens the
  // autocomplete.
  const match = upToCaret.match(/(?:^|\s)@([\w.-]*)$/)
  return match ? match[1] : null
}

export default function MessageComposer({ members, onSend, isSending, disabled }: Props) {
  const [value, setValue] = useState('')
  const [caret, setCaret] = useState(0)
  const [highlighted, setHighlighted] = useState(0)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const query = activeMentionQuery(value, caret)

  const suggestions = useMemo(() => {
    if (query === null) return []
    const needle = query.toLowerCase()
    return members
      .filter((m) => m.username.toLowerCase().startsWith(needle))
      .slice(0, MAX_SUGGESTIONS)
  }, [query, members])

  const applySuggestion = (username: string) => {
    // Replace the partial handle the caret is sitting in, leaving whatever
    // follows the caret untouched.
    const before = value.slice(0, caret).replace(/@[\w.-]*$/, `@${username} `)
    const next = before + value.slice(caret)
    setValue(next)
    setCaret(before.length)
    requestAnimationFrame(() => {
      inputRef.current?.focus()
      inputRef.current?.setSelectionRange(before.length, before.length)
    })
  }

  const submit = () => {
    const body = value.trim()
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
        applySuggestion(suggestions[highlighted].username)
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
            {suggestions.map((m, i) => (
              <UnstyledButton
                key={m.user_id}
                onMouseDown={(e) => {
                  // mousedown, not click — click would blur the textarea first
                  // and lose the caret position we need.
                  e.preventDefault()
                  applySuggestion(m.username)
                }}
                onMouseEnter={() => setHighlighted(i)}
                p="xs"
                style={{
                  borderRadius: 'var(--mantine-radius-sm)',
                  background:
                    i === highlighted ? 'var(--mantine-color-dark-5)' : 'transparent',
                }}
              >
                <Text size="sm">@{m.username}</Text>
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
          placeholder={disabled ? 'Join this group to chat' : 'Message the group — @ to mention'}
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
