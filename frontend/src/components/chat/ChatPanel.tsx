import { Badge, Group, Paper, Skeleton, Stack, Text, Tooltip } from '@mantine/core'
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
}

export default function ChatPanel({ group, members }: Props) {
  const { user } = useAuth()
  const isMember = !!group.current_user_role
  const { online, onlineIds, isConnected } = useGroupPresence(group.id)

  // The panel being mounted is what enables the query — so the fallback poll
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
    <Paper withBorder radius="md" p="xs">
      <Stack gap="xs" h={520}>
        <Group justify="space-between" px="xs" pt={4}>
          <Group gap="xs">
            <Text size="sm" fw={600}>
              Group chat
            </Text>
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
          </Group>

          {!isConnected && (
            <Tooltip label="Live updates unavailable — falling back to periodic refresh">
              <Group gap={4} c="dimmed">
                <IconPlugConnectedX size={14} />
                <Text size="xs">Reconnecting</Text>
              </Group>
            </Tooltip>
          )}
        </Group>

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
    </Paper>
  )
}
