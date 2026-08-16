import { Badge, Group, Skeleton, Stack, Text, Tooltip } from '@mantine/core'
import { IconCircleFilled, IconPlugConnectedX } from '@tabler/icons-react'
import { notifications } from '@mantine/notifications'
import { useAuth } from '../../hooks/useAuth'
import { useChatMessages, useDeleteMessage, useGroupPresence, useSendMessage } from '../../hooks/useChat'
import { ApiError } from '../../services/apiClient'
import type { GroupDetailResponse, GroupMemberResponse } from '../../types/group'
import MessageComposer from './MessageComposer'
import MessageList from './MessageList'

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

  // Mounting this component is what enables the query — so the fallback poll
  // only ever runs while someone is actually looking at the chat.
  const { data: messages = [], isLoading } = useChatMessages(group.id, isMember)
  const sendMessage = useSendMessage(group.id)
  const deleteMessage = useDeleteMessage(group.id)

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
