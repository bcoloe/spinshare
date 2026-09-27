import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Group, Modal, Stack, Text, ThemeIcon } from '@mantine/core'
import { IconSparkles } from '@tabler/icons-react'
import { usePendingRecaps, useMarkRecapSeen } from '../../hooks/useRecaps'

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
 * Shows a pop-up on a group's page when that group has a weekly recap the
 * member hasn't seen yet. Each group is handled independently: dismissing (or
 * viewing) marks only this group's recap as seen server-side, so the member's
 * other groups still prompt on their next visit.
 */
export default function RecapPopup({ groupId }: { groupId: number }) {
  const navigate = useNavigate()
  const { data: pending = [] } = usePendingRecaps(true)
  const markSeen = useMarkRecapSeen()
  const recap = pending.find((r) => r.group_id === groupId)
  // Tracks the recap already surfaced so the modal opens once per recap even
  // while the pending query refetches (GroupPage isn't remounted on group switch).
  const [shownRecapId, setShownRecapId] = useState<number | null>(null)
  const [opened, setOpened] = useState(false)

  useEffect(() => {
    if (recap && recap.id !== shownRecapId) {
      setShownRecapId(recap.id)
      setOpened(true)
    }
  }, [recap, shownRecapId])

  if (!recap) return null

  const handleDismiss = () => {
    markSeen.mutate({ groupId: recap.group_id, recapId: recap.id })
    setOpened(false)
  }

  const handleView = () => {
    handleDismiss()
    // ?recap=open tells GroupInfo to auto-open the recap overlay on arrival.
    navigate(`/groups/${recap.group_id}?tab=info&recap=open`)
  }

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
        <Text size="sm">
          The weekly recap for <strong>{recap.group_name}</strong> (
          {formatWeekRange(recap.week_start, recap.week_end)}) is ready. See who added and
          reviewed the most, the week's favorite album, and how the group did at guessing.
        </Text>
        <Group justify="flex-end" gap="sm">
          <Button variant="subtle" color="gray" onClick={handleDismiss}>
            Dismiss
          </Button>
          <Button onClick={handleView} leftSection={<IconSparkles size={16} />}>
            View recap
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
