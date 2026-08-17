import { Fragment, useEffect, useRef } from 'react'
import { ActionIcon, Avatar, Group, Loader, Stack, Text, Tooltip } from '@mantine/core'
import { IconTrash } from '@tabler/icons-react'
import { useNavigate } from 'react-router-dom'
import type { MessageResponse } from '../../types/message'

/** How close to the top counts as "asking for more". */
const LOAD_OLDER_THRESHOLD_PX = 60

interface Props {
  messages: MessageResponse[]
  currentUserId: number | undefined
  currentUsername: string | undefined
  canModerate: boolean
  onlineIds: Set<number>
  onDelete: (messageId: number) => void
  /** Whether a page of older messages may still exist above the current window. */
  hasOlder: boolean
  isLoadingOlder: boolean
  onLoadOlder: () => void
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

function formatDay(iso: string): string {
  const date = new Date(iso)
  const today = new Date()
  const isToday = date.toDateString() === today.toDateString()
  if (isToday) return 'Today'
  return date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })
}

/**
 * Render a message body with its mentions highlighted.
 *
 * Spans come from the server's resolved `mentions` list — the body text itself
 * is never parsed for handles here. That means an unresolvable or spoofed
 * `@handle` renders as the plain text it is, and only people the backend
 * actually authorised as group members can appear as a real mention.
 */
function renderBody(message: MessageResponse, currentUsername: string | undefined) {
  if (message.mentions.length === 0) return message.body

  const known = new Map(message.mentions.map((m) => [m.username.toLowerCase(), m]))
  // Split on handle-shaped runs, then keep only the ones the server confirmed.
  const parts = message.body.split(/(@[\w.-]+)/g)

  return parts.map((part, i) => {
    if (!part.startsWith('@')) return <Fragment key={i}>{part}</Fragment>

    const mention = known.get(part.slice(1).toLowerCase())
    if (!mention) return <Fragment key={i}>{part}</Fragment>

    const isMe = currentUsername?.toLowerCase() === mention.username.toLowerCase()
    return (
      <Text
        key={i}
        span
        fw={600}
        c={isMe ? 'violet.3' : 'violet.5'}
        style={
          isMe
            ? {
                background: 'var(--mantine-color-violet-9)',
                borderRadius: 'var(--mantine-radius-sm)',
                padding: '0 3px',
              }
            : undefined
        }
      >
        {part}
      </Text>
    )
  })
}

export default function MessageList({
  messages,
  currentUserId,
  currentUsername,
  canModerate,
  onlineIds,
  onDelete,
  hasOlder,
  isLoadingOlder,
  onLoadOlder,
}: Props) {
  const navigate = useNavigate()
  const bottomRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  // Only auto-scroll when the reader is already at the bottom, so a new message
  // never yanks someone out of the scrollback they're reading.
  const pinnedToBottom = useRef(true)
  // Scroll height captured just before a backwards page is requested, so the
  // prepended messages can be offset back out again.
  const anchorHeight = useRef<number | null>(null)
  const firstMessageId = useRef<number | null>(null)

  const handleScroll = () => {
    const el = containerRef.current
    if (!el) return
    pinnedToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80

    if (el.scrollTop < LOAD_OLDER_THRESHOLD_PX && hasOlder && !isLoadingOlder) {
      anchorHeight.current = el.scrollHeight
      onLoadOlder()
    }
  }

  useEffect(() => {
    const el = containerRef.current
    const first = messages[0]?.id ?? null
    // A smaller leading id means a page was prepended rather than appended.
    const prepended =
      firstMessageId.current !== null && first !== null && first < firstMessageId.current
    firstMessageId.current = first

    if (prepended && el && anchorHeight.current !== null) {
      // Push the viewport down by exactly the height that was inserted above
      // it, so the reader stays on the message they were looking at instead of
      // being thrown to the top of the newly loaded page.
      el.scrollTop += el.scrollHeight - anchorHeight.current
      anchorHeight.current = null
      return
    }

    if (pinnedToBottom.current) {
      bottomRef.current?.scrollIntoView({ block: 'end' })
    }
  }, [messages])

  if (messages.length === 0) {
    return (
      <Stack align="center" justify="center" h="100%" gap={4}>
        <Text size="sm" c="dimmed">
          No messages yet
        </Text>
        <Text size="xs" c="dimmed">
          Start the conversation about today's spin.
        </Text>
      </Stack>
    )
  }

  let lastDay = ''

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      style={{ overflowY: 'auto', height: '100%' }}
    >
      <Stack gap="xs" p="xs">
        {isLoadingOlder ? (
          <Group justify="center" py="xs">
            <Loader size="xs" />
          </Group>
        ) : !hasOlder ? (
          <Text size="xs" c="dimmed" ta="center" py="xs">
            Beginning of the conversation
          </Text>
        ) : null}

        {messages.map((message) => {
          const day = formatDay(message.created_at)
          const showDay = day !== lastDay
          lastDay = day

          const isMine = message.user_id !== null && message.user_id === currentUserId
          const canDelete = !message.is_deleted && (isMine || canModerate)
          const mentionsMe =
            currentUserId !== undefined &&
            message.mentions.some((m) => m.user_id === currentUserId)

          return (
            <Fragment key={message.id}>
              {showDay && (
                <Text size="xs" c="dimmed" ta="center" mt="xs">
                  {day}
                </Text>
              )}

              <Group
                gap="xs"
                align="flex-start"
                wrap="nowrap"
                px="xs"
                py={4}
                style={{
                  borderRadius: 'var(--mantine-radius-sm)',
                  // A message that pings you is worth finding at a glance.
                  background: mentionsMe ? 'var(--mantine-color-dark-6)' : undefined,
                  borderLeft: mentionsMe
                    ? '2px solid var(--mantine-color-violet-5)'
                    : '2px solid transparent',
                }}
              >
                <Avatar
                  size="sm"
                  radius="xl"
                  color={message.username ? 'violet' : 'gray'}
                  style={
                    message.user_id !== null && onlineIds.has(message.user_id)
                      ? { outline: '2px solid var(--mantine-color-teal-5)' }
                      : undefined
                  }
                >
                  {message.username ? message.username[0].toUpperCase() : '?'}
                </Avatar>

                <Stack gap={0} flex={1} style={{ minWidth: 0 }}>
                  <Group gap="xs">
                    {message.username ? (
                      <Text
                        size="sm"
                        fw={600}
                        style={{ cursor: 'pointer' }}
                        onClick={() => navigate(`/users/${message.username}`)}
                      >
                        {message.username}
                      </Text>
                    ) : (
                      <Text size="sm" fw={600} c="dimmed" fs="italic">
                        [deleted user]
                      </Text>
                    )}
                    <Text size="xs" c="dimmed">
                      {formatTime(message.created_at)}
                    </Text>
                  </Group>

                  {message.is_deleted ? (
                    <Text size="sm" c="dimmed" fs="italic">
                      [message deleted]
                    </Text>
                  ) : (
                    <Text size="sm" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                      {renderBody(message, currentUsername)}
                    </Text>
                  )}
                </Stack>

                {canDelete && (
                  <Tooltip label="Delete message">
                    <ActionIcon
                      size="sm"
                      variant="subtle"
                      color="red"
                      aria-label="Delete message"
                      onClick={() => onDelete(message.id)}
                    >
                      <IconTrash size={13} />
                    </ActionIcon>
                  </Tooltip>
                )}
              </Group>
            </Fragment>
          )
        })}
        <div ref={bottomRef} />
      </Stack>
    </div>
  )
}
