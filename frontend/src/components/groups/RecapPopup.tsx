import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Group, List, Modal, Stack, Text, ThemeIcon } from '@mantine/core'
import { IconSparkles } from '@tabler/icons-react'
import { usePendingRecaps, useMarkRecapSeen } from '../../hooks/useRecaps'
import type { RecapSummary } from '../../types/recap'

// Parse "YYYY-MM-DD" as a local date and render a "Jul 27 – Aug 2" range
// (week_end is exclusive, so the inclusive last day is one earlier).
function formatWeekRange(weekStart: string, weekEnd: string): string {
  const parse = (iso: string) => {
    const [y, m, d] = iso.split('-').map(Number)
    return new Date(y, m - 1, d)
  }
  const fmt = (date: Date) => date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  const start = parse(weekStart)
  const end = parse(weekEnd)
  end.setDate(end.getDate() - 1)
  return `${fmt(start)} – ${fmt(end)}`
}

/**
 * Shows a one-time-per-session pop-up the first time a member returns after a
 * new weekly recap has been generated. Dismissing (or viewing) marks the shown
 * recaps as seen server-side so it won't reappear.
 */
export default function RecapPopup() {
  const navigate = useNavigate()
  const { data: pending = [] } = usePendingRecaps(true)
  const markSeen = useMarkRecapSeen()
  const [opened, setOpened] = useState(false)
  const [handled, setHandled] = useState(false)

  useEffect(() => {
    if (!handled && pending.length > 0) {
      setOpened(true)
      setHandled(true)
    }
  }, [pending, handled])

  const markAllSeen = () => {
    for (const r of pending) {
      markSeen.mutate({ groupId: r.group_id, recapId: r.id })
    }
  }

  const handleDismiss = () => {
    markAllSeen()
    setOpened(false)
  }

  const handleView = (recap: RecapSummary) => {
    markAllSeen()
    setOpened(false)
    // ?recap=open tells GroupInfo to auto-open the recap overlay on arrival.
    navigate(`/groups/${recap.group_id}?tab=info&recap=open`)
  }

  if (pending.length === 0) return null
  const primary = pending[0]

  return (
    <Modal
      opened={opened}
      onClose={handleDismiss}
      title={
        <Group gap="xs">
          <ThemeIcon variant="light" color="violet" radius="xl" size="sm">
            <IconSparkles size={14} />
          </ThemeIcon>
          <Text fw={600}>Your week is ready</Text>
        </Group>
      }
      centered
    >
      <Stack gap="md">
        {pending.length === 1 ? (
          <Text size="sm">
            The weekly recap for <strong>{primary.group_name}</strong> (
            {formatWeekRange(primary.week_start, primary.week_end)}) is ready. See who
            added and reviewed the most, the week's favorite album, and how the group did
            at guessing.
          </Text>
        ) : (
          <>
            <Text size="sm">Fresh weekly recaps are ready for your groups:</Text>
            <List spacing="xs" size="sm">
              {pending.map((r) => (
                <List.Item key={r.id}>
                  <strong>{r.group_name}</strong> · {formatWeekRange(r.week_start, r.week_end)}
                </List.Item>
              ))}
            </List>
          </>
        )}
        <Group justify="flex-end" gap="sm">
          <Button variant="subtle" color="gray" onClick={handleDismiss}>
            Dismiss
          </Button>
          <Button onClick={() => handleView(primary)} leftSection={<IconSparkles size={16} />}>
            View recap
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
