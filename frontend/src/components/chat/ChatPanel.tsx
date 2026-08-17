import { useEffect, useRef } from 'react'
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
 * How long to let a burst of messages settle before persisting the read marker.
 * Short enough that closing the panel right after reading still records it.
 */
const SEEN_DEBOUNCE_MS = 800

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

  // Acknowledged up to this message id. Null means "nothing acknowledged for
  // this group yet", which is what makes opening the chat clear whatever was
  // already waiting.
  const acknowledged = useRef<number | null>(null)
  useEffect(() => {
    acknowledged.current = null
  }, [group.id])

  useEffect(() => {
    // Deliberately does not fire while the tab is backgrounded: a message that
    // arrives then is still unread, and stays counted until the user comes back
    // to the conversation.
    if (!isWatching) return
    if (acknowledged.current === latestMessageId) return

    // Debounced because the marker now advances on every message rather than
    // only on mentions — a brisk exchange would otherwise be one write per
    // message. The cleanup restarts the timer, so a burst settles into one call.
    const timer = setTimeout(() => {
      acknowledged.current = latestMessageId
      // An empty room has no message to mark, but its mentions can still clear.
      markSeen.mutate(latestMessageId || undefined)
    }, SEEN_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [isWatching, latestMessageId, markSeen.mutate])

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
