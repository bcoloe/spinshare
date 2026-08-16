import { ActionIcon, Group, Paper, Text, Tooltip } from '@mantine/core'
import { useMediaQuery } from '@mantine/hooks'
import { IconChevronDown, IconPlugConnectedX, IconX } from '@tabler/icons-react'
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
  minimized: boolean
  onClose: () => void
  onToggleMinimize: () => void
}

/**
 * Chat as a floating panel rather than a page or a tab.
 *
 * Non-modal by design — no scrim, no focus trap — so the group page stays fully
 * usable underneath. The point is to chat *while* reviewing an album or reading
 * history, which a tab or a modal drawer would both prevent.
 *
 * The panel is kept mounted (hidden) while minimized so the message cache and
 * scroll position survive collapsing, and so the fallback poll isn't restarted
 * from scratch every time it reopens.
 */
export default function ChatOverlay({
  group,
  members,
  opened,
  minimized,
  onClose,
  onToggleMinimize,
}: Props) {
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
        height: minimized ? 'auto' : '70vh',
        zIndex: 200,
        borderRadius: 'var(--mantine-radius-md) var(--mantine-radius-md) 0 0',
      }
    : {
        position: 'fixed',
        right: EDGE_GAP,
        bottom: footerOffset + EDGE_GAP,
        width: PANEL_WIDTH,
        height: minimized ? 'auto' : Math.min(PANEL_HEIGHT, window.innerHeight - 160),
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
          borderBottom: minimized ? 'none' : '1px solid var(--mantine-color-dark-4)',
          // The whole bar collapses the panel, so there's a large hit target
          // rather than only the small chevron.
          cursor: 'pointer',
          flexShrink: 0,
        }}
        onClick={onToggleMinimize}
      >
        <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
          <Text size="sm" fw={600} truncate>
            {group.name}
          </Text>
          <PresenceBadge groupId={group.id} />
        </Group>

        <Group gap={2} wrap="nowrap" onClick={(e) => e.stopPropagation()}>
          {!isConnected && (
            <Tooltip label="Live updates unavailable — falling back to periodic refresh">
              <IconPlugConnectedX size={14} color="var(--mantine-color-dimmed)" />
            </Tooltip>
          )}
          <Tooltip label={minimized ? 'Expand chat' : 'Collapse chat'}>
            <ActionIcon
              size="sm"
              variant="subtle"
              color="gray"
              aria-label={minimized ? 'Expand chat' : 'Collapse chat'}
              onClick={onToggleMinimize}
            >
              <IconChevronDown
                size={16}
                style={{
                  transform: minimized ? 'rotate(180deg)' : undefined,
                  transition: 'transform 150ms ease',
                }}
              />
            </ActionIcon>
          </Tooltip>
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

      {/* Kept mounted while minimized so cache and scroll position survive. */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          padding: 'var(--mantine-spacing-xs)',
          display: minimized ? 'none' : 'block',
        }}
      >
        <ChatPanel
          group={group}
          members={members}
          showPresence={false}
          active={!minimized}
        />
      </div>
    </Paper>
  )
}
