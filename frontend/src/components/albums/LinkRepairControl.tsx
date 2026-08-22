import { Button, Group } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { IconFlag, IconPencil } from '@tabler/icons-react'
import EditLinksModal from './EditLinksModal'
import ReportLinkModal from './ReportLinkModal'
import { useAuth } from '../../hooks/useAuth'
import type { AlbumResponse } from '../../types/album'

interface Props {
  album: AlbumResponse
  size?: 'xs' | 'sm'
  /** Extra top margin, for callers stacking this under other content. */
  mt?: number
}

/**
 * The per-album link repair entry point: admins edit links directly, everyone
 * else files a report for an admin to review.
 *
 * Bundled with its modals so any surface showing an album's links can offer
 * repair with one line, rather than each page re-wiring auth checks, disclosure
 * state and two modals of its own.
 */
export default function LinkRepairControl({ album, size = 'xs', mt }: Props) {
  const { user } = useAuth()
  const [editOpened, { open: openEdit, close: closeEdit }] = useDisclosure(false)
  const [reportOpened, { open: openReport, close: closeReport }] = useDisclosure(false)

  // Anonymous visitors get nothing — reporting requires an account to attribute
  // the report to, and the API rejects it anyway.
  if (!user) return null

  // Wrapped in a Group so the button hugs the left edge rather than stretching,
  // since callers place this inside a Stack (which stretches children).
  return (
    <Group gap="xs">
      {user.is_admin ? (
        <>
          <Button
            variant="subtle"
            color="orange"
            size={size}
            leftSection={<IconPencil size={13} />}
            onClick={openEdit}
            mt={mt}
          >
            Edit links
          </Button>
          <EditLinksModal opened={editOpened} onClose={closeEdit} album={album} />
        </>
      ) : (
        <>
          <Button
            variant="subtle"
            color="gray"
            size={size}
            leftSection={<IconFlag size={13} />}
            onClick={openReport}
            mt={mt}
          >
            Report link issue
          </Button>
          <ReportLinkModal opened={reportOpened} onClose={closeReport} album={album} />
        </>
      )}
    </Group>
  )
}
