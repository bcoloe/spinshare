import { Button, Modal, Radio, Select, Stack, Text, Textarea, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { useSubmitLinkReport } from '../../hooks/useAdmin'
import { ApiError } from '../../services/apiClient'
import type { AlbumResponse } from '../../types/album'
import {
  LINK_FIELD_TO_COLUMN,
  LINK_LABELS,
  REASON_OPTIONS,
  type ReportableLink,
  type ReportReason,
} from '../../types/linkReport'

interface Props {
  opened: boolean
  onClose: () => void
  album: AlbumResponse
}

interface FormValues {
  link_field: ReportableLink
  reason_code: ReportReason
  reason_detail: string
  suggested_url: string
}

const LINK_ORDER: ReportableLink[] = [
  'spotify',
  'apple_music',
  'youtube_music',
  'bandcamp',
  'wikipedia',
]

/** Placeholder shown for the suggestion field, per service. */
const URL_HINTS: Record<ReportableLink, string> = {
  spotify: 'https://open.spotify.com/album/…',
  apple_music: 'https://music.apple.com/us/album/…',
  youtube_music: 'https://music.youtube.com/browse/…',
  bandcamp: 'https://artist.bandcamp.com/album/…',
  wikipedia: 'https://en.wikipedia.org/wiki/…',
}

/**
 * Lets a non-admin flag a bad link for admin review.
 *
 * The suggestion is optional and is normalised server-side, so a pasted share
 * link is fine and no URL parsing happens here.
 */
export default function ReportLinkModal({ opened, onClose, album }: Props) {
  const submitReport = useSubmitLinkReport(album.id)

  const form = useForm<FormValues>({
    initialValues: {
      link_field: 'spotify',
      reason_code: 'bad',
      reason_detail: '',
      suggested_url: '',
    },
    validate: {
      // Detail is optional even for "other" — a category alone is a useful
      // report, and demanding prose only suppresses reports.
      reason_detail: (v) => (v.length > 1000 ? 'Max 1000 characters' : null),
    },
  })

  // A missing link is a legitimate thing to report, so absent options stay
  // selectable — they're just annotated so the reporter knows what they're seeing.
  const options = LINK_ORDER.map((link) => {
    const current = album[LINK_FIELD_TO_COLUMN[link] as keyof AlbumResponse]
    return {
      value: link,
      label: current ? LINK_LABELS[link] : `${LINK_LABELS[link]} (currently empty)`,
    }
  })

  const handleSubmit = async (values: FormValues) => {
    try {
      await submitReport.mutateAsync({
        link_field: values.link_field,
        reason_code: values.reason_code,
        reason_detail: values.reason_detail.trim() || null,
        suggested_url: values.suggested_url.trim() || null,
      })
      notifications.show({
        color: 'green',
        title: 'Report submitted',
        message: 'An admin will review this link. Thanks!',
      })
      form.reset()
      onClose()
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not submit report'
      notifications.show({ color: 'red', message })
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title="Report a bad link" centered>
      <form onSubmit={form.onSubmit(handleSubmit)}>
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            {album.title} — {album.artist}
          </Text>
          <Select
            label="Which link is wrong?"
            data={options}
            allowDeselect={false}
            {...form.getInputProps('link_field')}
          />
          <Radio.Group
            label="What's wrong with it?"
            {...form.getInputProps('reason_code')}
          >
            <Stack gap="xs" mt="xs">
              {REASON_OPTIONS.map((o) => (
                <Radio
                  key={o.value}
                  value={o.value}
                  label={o.label}
                  description={o.hint}
                />
              ))}
            </Stack>
          </Radio.Group>
          {/* Only "other" gets a free-text box — the fixed reasons already say
              everything an admin needs, and an always-present textarea invites
              prose that duplicates the category. */}
          {form.values.reason_code === 'other' && (
            <Textarea
              label="Tell us more"
              description="Optional"
              placeholder="e.g. the link works but it is the wrong regional edition"
              minRows={3}
              autosize
              {...form.getInputProps('reason_detail')}
            />
          )}
          <TextInput
            label="Suggested replacement URL"
            description="Optional — paste the correct link if you have it"
            placeholder={URL_HINTS[form.values.link_field]}
            {...form.getInputProps('suggested_url')}
          />
          <Button type="submit" loading={submitReport.isPending}>
            Submit report
          </Button>
        </Stack>
      </form>
    </Modal>
  )
}
