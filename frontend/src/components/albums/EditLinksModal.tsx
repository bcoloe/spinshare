import { useEffect, useState } from 'react'
import {
  ActionIcon,
  Anchor,
  Button,
  Group,
  Modal,
  Stack,
  Text,
  TextInput,
  Tooltip,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { IconExternalLink, IconX } from '@tabler/icons-react'
import { useQueryClient } from '@tanstack/react-query'
import { albumService } from '../../services/albumService'
import { ApiError } from '../../services/apiClient'
import type { AlbumResponse } from '../../types/album'
import type { ReportableLink } from '../../types/linkReport'
import { albumLinkUrl } from '../../utils/albumLinkUrl'

/** The five editable link columns, in the order they appear in the form. */
export type LinkColumn =
  | 'spotify_album_id'
  | 'apple_music_album_id'
  | 'youtube_music_id'
  | 'artist_url'
  | 'wikipedia_url'

interface FormValues {
  spotify_album_id: string
  apple_music_album_id: string
  youtube_music_id: string
  artist_url: string
  wikipedia_url: string
}

interface Props {
  opened: boolean
  onClose: () => void
  album: Pick<AlbumResponse, 'id'> & Partial<Record<LinkColumn, string | null>>
  /** Pre-fill specific fields, e.g. with a value suggested in a link report. */
  initialOverrides?: Partial<Record<LinkColumn, string | null>>
  /** Field to visually call out, e.g. the one a report is about. */
  highlightField?: LinkColumn
  /** Shown under the highlighted field, e.g. "Suggested by alice". */
  highlightNote?: string
  onSaved?: () => void | Promise<void>
}

const FIELDS: {
  name: LinkColumn
  link: ReportableLink
  label: string
  placeholder: string
}[] = [
  {
    name: 'spotify_album_id',
    link: 'spotify',
    label: 'Spotify album link or ID',
    placeholder: 'https://open.spotify.com/album/…',
  },
  {
    name: 'apple_music_album_id',
    link: 'apple_music',
    label: 'Apple Music album link or ID',
    placeholder: 'https://music.apple.com/us/album/…',
  },
  {
    name: 'youtube_music_id',
    link: 'youtube_music',
    label: 'YouTube Music link or browse ID',
    placeholder: 'https://music.youtube.com/browse/…',
  },
  {
    name: 'artist_url',
    link: 'bandcamp',
    label: 'Bandcamp album URL',
    placeholder: 'https://artist.bandcamp.com/album/name',
  },
  {
    name: 'wikipedia_url',
    link: 'wikipedia',
    label: 'Wikipedia URL',
    placeholder: 'https://en.wikipedia.org/wiki/…',
  },
]

/**
 * Admin editor for an album's links.
 *
 * Share links are accepted alongside bare IDs; the backend normalises them, so
 * there is no duplicate URL parsing here. Clearing a field sends an explicit
 * null, which the API treats as "remove this link".
 */
export default function EditLinksModal({
  opened,
  onClose,
  album,
  initialOverrides,
  highlightField,
  highlightNote,
  onSaved,
}: Props) {
  const qc = useQueryClient()
  const [saving, setSaving] = useState(false)

  const form = useForm<FormValues>({
    initialValues: {
      spotify_album_id: '',
      apple_music_album_id: '',
      youtube_music_id: '',
      artist_url: '',
      wikipedia_url: '',
    },
  })

  // Reset to the album's current values (plus any overrides) each time it opens,
  // so a cancelled edit never leaks into the next one.
  useEffect(() => {
    if (!opened) return
    form.setValues({
      spotify_album_id: initialOverrides?.spotify_album_id ?? album.spotify_album_id ?? '',
      apple_music_album_id:
        initialOverrides?.apple_music_album_id ?? album.apple_music_album_id ?? '',
      youtube_music_id: initialOverrides?.youtube_music_id ?? album.youtube_music_id ?? '',
      artist_url: initialOverrides?.artist_url ?? album.artist_url ?? '',
      wikipedia_url: initialOverrides?.wikipedia_url ?? album.wikipedia_url ?? '',
    })
    // `form` is intentionally omitted — including it would re-run on every
    // keystroke and wipe what the admin is typing.
  }, [opened, album, initialOverrides])

  const handleSubmit = async (values: FormValues) => {
    setSaving(true)
    try {
      await albumService.updateLinks(album.id, {
        spotify_album_id: values.spotify_album_id || null,
        apple_music_album_id: values.apple_music_album_id || null,
        youtube_music_id: values.youtube_music_id || null,
        artist_url: values.artist_url || null,
        wikipedia_url: values.wikipedia_url || null,
      })
      await qc.invalidateQueries({ queryKey: ['albums', album.id] })
      await onSaved?.()
      onClose()
      notifications.show({ color: 'green', message: 'Album links updated' })
    } catch (err) {
      // The backend's link errors are written to be read by a person — e.g.
      // "That looks like an Apple Music link" — so surface them as-is.
      const message = err instanceof ApiError ? err.message : 'Could not update album links'
      notifications.show({ color: 'red', message })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title="Edit Album Links" size="md">
      <form onSubmit={form.onSubmit(handleSubmit)}>
        <Stack gap="sm">
          <Text size="xs" c="dimmed">
            Paste a share link or an ID. Clear a field and save to remove that link.
          </Text>
          {FIELDS.map((f) => {
            const value = form.values[f.name]
            // Preview whatever is in the box right now rather than the saved
            // value, so a suggestion can be checked before it is committed to.
            const preview = albumLinkUrl(f.link, value)
            const saved = album[f.name] ?? ''
            // A prefilled suggestion overwrites the field, so without this the
            // admin cannot see what they would be replacing.
            const changed = value.trim() !== saved.trim()
            return (
              <Stack key={f.name} gap={4}>
              <TextInput
                label={f.label}
                placeholder={f.placeholder}
                description={highlightField === f.name ? highlightNote : undefined}
                styles={
                  highlightField === f.name
                    ? { input: { borderColor: 'var(--mantine-color-orange-6)' } }
                    : undefined
                }
                rightSectionWidth={64}
                rightSection={
                  <Group gap={2} wrap="nowrap" pr={4}>
                    <Tooltip label={preview ? 'Open in a new tab' : 'Nothing to preview'}>
                      {/* span so the tooltip still fires while the icon is disabled */}
                      <span>
                        <ActionIcon
                          variant="subtle"
                          color={highlightField === f.name ? 'orange' : 'gray'}
                          component="a"
                          href={preview ?? undefined}
                          target="_blank"
                          rel="noopener noreferrer"
                          data-disabled={!preview || undefined}
                          onClick={(e) => {
                            if (!preview) e.preventDefault()
                          }}
                          aria-label={`Preview ${f.label}`}
                        >
                          <IconExternalLink size={15} />
                        </ActionIcon>
                      </span>
                    </Tooltip>
                    <Tooltip label="Remove this link">
                      <span>
                        <ActionIcon
                          variant="subtle"
                          color="red"
                          disabled={!value}
                          onClick={() => form.setFieldValue(f.name, '')}
                          aria-label={`Remove ${f.label}`}
                        >
                          <IconX size={15} />
                        </ActionIcon>
                      </span>
                    </Tooltip>
                  </Group>
                }
                {...form.getInputProps(f.name)}
              />
              {changed && (
                <PreviousValue
                  link={f.link}
                  value={saved}
                  label={f.label}
                  onRevert={() => form.setFieldValue(f.name, saved)}
                />
              )}
              </Stack>
            )
          })}
          <Group justify="flex-end" mt="xs">
            <Button variant="subtle" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" loading={saving}>
              Save
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  )
}

/**
 * The value a field is about to replace, shown inline under the input.
 *
 * Without this the old link is simply gone from view the moment a suggestion is
 * prefilled, which is precisely when an admin needs to compare the two. Revert
 * puts it back for the case where the suggestion turns out to be wrong.
 */
function PreviousValue({
  link,
  value,
  label,
  onRevert,
}: {
  link: ReportableLink
  value: string
  label: string
  onRevert: () => void
}) {
  const href = albumLinkUrl(link, value)

  return (
    <Group gap={6} wrap="nowrap" pl={2}>
      <Text size="xs" c="dimmed" style={{ flexShrink: 0 }}>
        Was
      </Text>
      {!value ? (
        <Text size="xs" c="dimmed" fs="italic" style={{ flexShrink: 0 }}>
          empty
        </Text>
      ) : href ? (
        <Anchor
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          size="xs"
          c="dimmed"
          lineClamp={1}
          aria-label={`Preview previous ${label}`}
          style={{ textDecoration: 'line-through' }}
        >
          {value}
        </Anchor>
      ) : (
        <Text size="xs" c="dimmed" td="line-through" lineClamp={1}>
          {value}
        </Text>
      )}
      <Anchor
        component="button"
        type="button"
        size="xs"
        onClick={onRevert}
        style={{ flexShrink: 0 }}
      >
        Revert
      </Anchor>
    </Group>
  )
}
