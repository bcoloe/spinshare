import { useEffect, useMemo, useRef } from 'react'
import { Badge, Group, Skeleton, Stack, Text, Tooltip } from '@mantine/core'
import { IconCircleFilled, IconPlugConnectedX } from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import { useDocumentVisibility } from '@mantine/hooks'
import { useAuth } from '../../hooks/useAuth'
import {
  CHAT_PAGE_SIZE,
  useChatMessages,
  useDeleteMessage,
  useGroupPresence,
  useChatSocket,
  useLoadOlderMessages,
  useMarkChatSeen,
  useSendMessage,
} from '../../hooks/useChat'
import { ApiError } from '../../services/apiClient'
import type { GroupDetailResponse, GroupMemberResponse } from '../../types/group'
import MessageComposer from './MessageComposer'
import MessageList from './MessageList'

/**
 * How often an open conversation records its read position as a fallback.
 *
 * The real triggers are opening and closing the panel; this only covers the
 * sessions that never get to close cleanly — a killed tab, a sleeping laptop.
 * Long enough that sitting in chat all afternoon is a handful of writes.
 */
const SEEN_SAFETY_NET_MS = 60_000

interface Props {
  group: GroupDetailResponse
  members: GroupMemberResponse[]
  /** Hidden when the surrounding chrome already shows presence (the overlay header). */
  showPresence?: boolean
}

/**
 * The chat conversation itself — list plus composer.
 *
 * Deliberately chrome-free and height-agnostic so it can be dropped into any
 * container. `ChatOverlay` supplies the floating frame; this stays reusable if
 * chat ever needs a full-page or embedded home too.
 */
export default function ChatPanel({ group, members, showPresence = true }: Props) {
  const { user } = useAuth()
  const isMember = !!group.current_user_role
  const { online, onlineIds, isConnected } = useGroupPresence(group.id)
  const documentVisibility = useDocumentVisibility()

  // Mounting this component is what enables the query — so the fallback poll
  // only ever runs while someone is actually looking at the chat.
  const { data: messages = [], isLoading } = useChatMessages(group.id, isMember)
  const sendMessage = useSendMessage(group.id)
  const deleteMessage = useDeleteMessage(group.id)
  const { loadOlder, isLoadingOlder, hasOlder } = useLoadOlderMessages(group.id)

  // Until a backwards page has actually come back we cannot know whether more
  // exists, so assume a full first page means there is. A wrong guess here
  // costs one request that returns nothing and settles the question honestly.
  const canLoadOlder = hasOlder ?? messages.length >= CHAT_PAGE_SIZE

  const markSeen = useMarkChatSeen(group.id)
  const { setActiveGroup } = useChatSocket()
  // Mounted means on screen — the panel unmounts when the chat closes — but a
  // backgrounded tab is still not being read.
  const isWatching = isMember && documentVisibility === 'visible'

  // Claim this group while the panel is up, so messages arriving in the
  // conversation the user is watching are not counted as unread behind it.
  useEffect(() => {
    setActiveGroup(group.id)
    return () => setActiveGroup(null)
  }, [group.id, setActiveGroup])

  const latestMessageId = messages.length ? messages[messages.length - 1].id : 0

  // The newest message that pings this user. Mentions are the one thing worth
  // writing promptly for, because clearing them is what empties the bell — and
  // they are rare enough to cost nothing.
  const latestMentionId = useMemo(() => {
    if (!user) return 0
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].mentions.some((m) => m.user_id === user.id)) return messages[i].id
    }
    return 0
  }, [messages, user])

  // Acknowledged up to this message id. Null means "nothing acknowledged for
  // this group yet", which is what makes opening the chat clear whatever was
  // already waiting.
  const acknowledged = useRef<number | null>(null)
  useEffect(() => {
    acknowledged.current = null
  }, [group.id])

  // Held in a ref so every trigger below reads the current position without
  // each of them having to re-subscribe when a message arrives — which is the
  // whole point: a message landing must not itself cause a write.
  const flushRef = useRef<() => void>(() => {})
  flushRef.current = () => {
    if (!isMember) return
    if (acknowledged.current === latestMessageId) return
    acknowledged.current = latestMessageId
    // An empty room has no message to mark, but its mentions can still clear.
    markSeen.mutate(latestMessageId || undefined)
  }

  // Opening the conversation, and returning to the tab. Deliberately not on
  // every message: while the panel is open the badge is already clear locally,
  // so the marker only has to be durable, not instant.
  //
  // Waits for the first page, since flushing before it lands would spend a
  // write recording a position we do not know yet.
  useEffect(() => {
    if (!isWatching || isLoading) return
    flushRef.current()
  }, [isWatching, isLoading])

  // A mention is the exception — the bell should empty while they are reading.
  useEffect(() => {
    if (!isWatching || !latestMentionId) return
    flushRef.current()
  }, [isWatching, latestMentionId])

  // Safety net for a long reading session. A tab that is closed abruptly, or a
  // laptop that sleeps, never runs the cleanup below, so progress would
  // otherwise be lost back to whatever was last recorded.
  useEffect(() => {
    if (!isWatching) return
    const timer = setInterval(() => flushRef.current(), SEEN_SAFETY_NET_MS)
    return () => clearInterval(timer)
  }, [isWatching])

  // Leaving the conversation — the ordinary path, and the one that records the
  // final position.
  useEffect(() => () => flushRef.current(), [group.id])

  const canModerate =
    group.current_user_role === 'owner' || group.current_user_role === 'admin'

  const handleSend = async (body: string) => {
    try {
      await sendMessage.mutateAsync(body)
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not send message'
      notifications.show({ color: 'red', message })
    }
  }

  const handleDelete = async (messageId: number) => {
    try {
      await deleteMessage.mutateAsync(messageId)
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not delete message'
      notifications.show({ color: 'red', message })
    }
  }

  const onlineLabel =
    online.length > 0
      ? online.map((m) => m.username).join(', ')
      : 'Nobody else is here right now'

  return (
    <Stack gap="xs" h="100%">
      {showPresence && (
        <Group justify="space-between" px="xs">
          <Tooltip label={onlineLabel} multiline maw={280}>
            <Badge
              size="sm"
              variant="light"
              color={online.length > 0 ? 'teal' : 'gray'}
              leftSection={<IconCircleFilled size={7} />}
            >
              {online.length} online
            </Badge>
          </Tooltip>

          {!isConnected && (
            <Tooltip label="Live updates unavailable — falling back to periodic refresh">
              <Group gap={4} c="dimmed">
                <IconPlugConnectedX size={14} />
                <Text size="xs">Reconnecting</Text>
              </Group>
            </Tooltip>
          )}
        </Group>
      )}

      <div style={{ flex: 1, minHeight: 0 }}>
        {isLoading ? (
          <Stack gap="xs" p="xs">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} h={36} radius="sm" />
            ))}
          </Stack>
        ) : (
          <MessageList
            messages={messages}
            currentUserId={user?.id}
            currentUsername={user?.username}
            canModerate={canModerate}
            onlineIds={onlineIds}
            onDelete={handleDelete}
            hasOlder={canLoadOlder}
            isLoadingOlder={isLoadingOlder}
            onLoadOlder={loadOlder}
          />
        )}
      </div>

      <MessageComposer
        members={members}
        onSend={handleSend}
        isSending={sendMessage.isPending}
        disabled={!isMember}
      />
    </Stack>
  )
}
