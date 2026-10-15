import { useCallback, useState } from 'react'
import { Button, Group, Slider, Stack, Text, Textarea } from '@mantine/core'
import { ratingColor } from '../../utils/ratingColor'
import { notifications } from '@mantine/notifications'
import { useSubmitReview, useUpdateReview } from '../../hooks/useDailySpin'
import { useDraftAutosave, type DraftContent } from '../../hooks/useDraftAutosave'
import { ApiError } from '../../services/apiClient'
import type { ReviewResponse } from '../../types/album'

interface Props {
  albumId: number
  existingReview: ReviewResponse | null
  /** False when the caller's review couldn't be loaded: its absence is then unknown. */
  reviewLoaded?: boolean
}

export default function ReviewForm({ albumId, existingReview, reviewLoaded = true }: Props) {
  const isDraft = !!existingReview?.is_draft
  const isPublished = !!existingReview && !isDraft
  const [editing, setEditing] = useState(false)

  const [rating, setRating] = useState<number | null>(existingReview?.rating ?? null)
  const [comment, setComment] = useState(existingReview?.comment ?? '')
  const submitReview = useSubmitReview(albumId)
  const updateReview = useUpdateReview(albumId)

  // A draft's starting content comes from the hook (the server copy, or a newer
  // local one); prefilling it here as well would overwrite typing. Editing a
  // published review loads its values from the Edit button instead.
  const loadDraft = useCallback((draft: DraftContent) => {
    setRating(draft.rating)
    setComment(draft.comment)
  }, [])
  const autosave = useDraftAutosave({
    albumId,
    existingReview,
    ready: reviewLoaded,
    content: { rating, comment },
    onLoad: loadDraft,
    submitReview,
    updateReview,
  })

  if (isPublished && !editing) {
    return (
      <Stack gap="xs">
        <Group justify="space-between" align="center">
          <Text size="sm" fw={600}>Your review</Text>
          <Button
            size="xs"
            variant="subtle"
            onClick={() => {
              setRating(existingReview.rating)
              setComment(existingReview.comment ?? '')
              setEditing(true)
            }}
          >
            Edit
          </Button>
        </Group>
        <Group gap="xs">
          <Text size="sm" c="dimmed">Rating:</Text>
          <Text size="sm" fw={500}>{existingReview.rating} / 10</Text>
        </Group>
        {existingReview.comment && (
          <Text size="sm" c="dimmed" fs="italic">&ldquo;{existingReview.comment}&rdquo;</Text>
        )}
      </Stack>
    )
  }

  const handleSaveDraft = async () => {
    autosave.markDirty() // an explicit save always goes to the server
    const result = await autosave.flush()
    if (result === 'failed') {
      notifications.show({ color: 'red', message: 'Could not save draft' })
    } else if (result === 'saved') {
      notifications.show({ color: 'teal', message: 'Draft saved' })
    }
  }

  const handleSubmit = async () => {
    if (rating === null) {
      notifications.show({ color: 'red', message: 'Please set a rating' })
      return
    }
    try {
      if (existingReview) {
        await updateReview.mutateAsync({
          reviewId: existingReview.id,
          data: { rating, comment: comment || undefined, is_draft: false },
        })
      } else {
        await submitReview.mutateAsync({ rating, comment: comment || undefined })
      }
      autosave.clearLocal()
      if (editing) setEditing(false)
      notifications.show({ color: 'green', message: existingReview ? 'Review updated' : 'Review submitted' })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not submit review'
      notifications.show({ color: 'red', message })
    }
  }

  const isLoading = submitReview.isPending || updateReview.isPending
  const title = isDraft ? 'Your draft review' : isPublished ? 'Edit your review' : 'Your review'

  return (
    <Stack gap="md" onBlur={autosave.onBlur}>
      <Text size="sm" fw={600}>{title}</Text>
      <div>
        <Group justify="space-between" mb={4}>
          <Text size="sm">Rating</Text>
          <Text size="sm" fw={500} c={ratingColor(rating)}>
            {rating !== null ? `${rating} / 10` : '—'}
          </Text>
        </Group>
        <Slider
          min={0}
          max={10}
          step={0.1}
          color={ratingColor(rating)}
          value={rating ?? 0}
          onChange={(v) => { autosave.markDirty(); setRating(v) }}
          marks={[0, 2, 4, 6, 8, 10].map((v) => ({ value: v, label: String(v) }))}
          mb="lg"
        />
      </div>
      <Textarea
        label="Comment (optional)"
        placeholder="What did you think?"
        value={comment}
        onChange={(e) => { autosave.markDirty(); setComment(e.currentTarget.value) }}
        maxLength={5000}
        autosize
        minRows={2}
      />
      <Group justify="space-between" align="center">
        <Group gap="xs">
          {!isPublished && (
            <Button variant="default" onClick={handleSaveDraft} loading={isLoading}>
              Save draft
            </Button>
          )}
          <Button onClick={handleSubmit} loading={isLoading} disabled={rating === null}>
            {isPublished ? 'Save' : 'Submit review'}
          </Button>
          {editing && (
            <Button variant="subtle" color="gray" onClick={() => setEditing(false)} disabled={isLoading}>
              Cancel
            </Button>
          )}
        </Group>
        {!isPublished && autosave.savedAt && (
          <Text size="xs" c="dimmed">
            Autosaved {autosave.savedAt.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
          </Text>
        )}
      </Group>
    </Stack>
  )
}
