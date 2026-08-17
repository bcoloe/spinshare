import { ActionIcon, Group, Paper, Text, Tooltip } from '@mantine/core'
import { useMediaQuery } from '@mantine/hooks'
import { IconPlugConnectedX, IconX } from '@tabler/icons-react'
import { useFooterOffset } from '../../hooks/useFooterOffset'
import { useGroupPresence } from '../../hooks/useChat'
import type { GroupDetailResponse, GroupMemberResponse } from '../../types/group'
import ChatPanel from './ChatPanel'
import PresenceBadge from './PresenceBadge'

const PANEL_WIDTH = 380
const PANEL_HEIGHT = 520
const EDGE_GAP = 24

interface Props {
  group: GroupDetailResponse
  members: GroupMemberResponse[]
  opened: boolean
  onClose: () => void
}

/**
 * Chat as a floating panel rather than a page or a tab.
 *
 * Non-modal by design — no scrim, no focus trap — so the group page stays fully
 * usable underneath. The point is to chat *while* reviewing an album or reading
 * history, which a tab or a modal drawer would both prevent.
 *
 * Open/closed is the only state: the launcher in the corner toggles it, and the
 * panel's own close button does the same thing. On mobile that close button is
 * the only way back out, since the launcher stands down under a full-width sheet.
 */
export default function ChatOverlay({ group, members, opened, onClose }: Props) {
  const isMobile = useMediaQuery('(max-width: 768px)')
  const footerOffset = useFooterOffset()
  const { isConnected } = useGroupPresence(group.id)

  if (!opened) return null

  // On mobile the panel spans the full width and docks to the bottom; on desktop
  // it floats in the bottom-right corner clear of the player footer.
  const frame: React.CSSProperties = isMobile
    ? {
        position: 'fixed',
        left: 0,
        right: 0,
        bottom: footerOffset,
        height: '70vh',
        zIndex: 200,
        borderRadius: 'var(--mantine-radius-md) var(--mantine-radius-md) 0 0',
      }
    : {
        position: 'fixed',
        right: EDGE_GAP,
        bottom: footerOffset + EDGE_GAP,
        width: PANEL_WIDTH,
        height: Math.min(PANEL_HEIGHT, window.innerHeight - 160),
        maxHeight: `calc(100vh - ${footerOffset + 120}px)`,
        zIndex: 200,
        borderRadius: 'var(--mantine-radius-md)',
      }

  return (
    <Paper withBorder shadow="xl" style={{ ...frame, display: 'flex', flexDirection: 'column' }}>
      <Group
        justify="space-between"
        px="sm"
        py="xs"
        wrap="nowrap"
        style={{
          borderBottom: '1px solid var(--mantine-color-dark-4)',
          flexShrink: 0,
        }}
      >
        <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
          <Text size="sm" fw={600} truncate>
            {group.name}
          </Text>
          <PresenceBadge groupId={group.id} />
        </Group>

        <Group gap={2} wrap="nowrap">
          {!isConnected && (
            <Tooltip label="Live updates unavailable — falling back to periodic refresh">
              <IconPlugConnectedX size={14} color="var(--mantine-color-dimmed)" />
            </Tooltip>
          )}
          <Tooltip label="Close chat">
            <ActionIcon
              size="sm"
              variant="subtle"
              color="gray"
              aria-label="Close chat"
              onClick={onClose}
            >
              <IconX size={16} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      <div
        style={{
          flex: 1,
          minHeight: 0,
          padding: 'var(--mantine-spacing-xs)',
        }}
      >
        <ChatPanel group={group} members={members} showPresence={false} />
      </div>
    </Paper>
  )
}
