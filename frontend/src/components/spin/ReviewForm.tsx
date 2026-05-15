import { useEffect, useRef, useState } from 'react'
import { Button, Group, Slider, Stack, Text, Textarea } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useSubmitReview, useUpdateReview } from '../../hooks/useDailySpin'
import { ApiError } from '../../services/apiClient'
import type { ReviewResponse } from '../../types/album'

interface Props {
  albumId: number
  existingReview: ReviewResponse | null
}

export default function ReviewForm({ albumId, existingReview }: Props) {
  const isDraft = !!existingReview?.is_draft
  const isPublished = !!existingReview && !isDraft
  const [editing, setEditing] = useState(false)

  const [rating, setRating] = useState<number | null>(existingReview?.rating ?? null)
  const [comment, setComment] = useState(existingReview?.comment ?? '')
  const submitReview = useSubmitReview(albumId)
  const updateReview = useUpdateReview(albumId)
  const [autosavedAt, setAutosavedAt] = useState<Date | null>(null)
  const isDirtyRef = useRef(false)
  const autosaveCallbackRef = useRef<() => Promise<void>>(() => Promise.resolve())

  useEffect(() => {
    if (existingReview) {
      setRating(existingReview.rating)
      setComment(existingReview.comment ?? '')
    }
  }, [existingReview?.id])

  autosaveCallbackRef.current = async () => {
    if (isPublished || submitReview.isPending || updateReview.isPending) return
    try {
      if (existingReview) {
        await updateReview.mutateAsync({
          reviewId: existingReview.id,
          data: { rating: rating ?? undefined, comment: comment || undefined, is_draft: true },
        })
      } else {
        await submitReview.mutateAsync({ rating: rating ?? undefined, comment: comment || undefined, is_draft: true })
      }
      setAutosavedAt(new Date())
    } catch {
      // autosave silently fails
    }
  }

  useEffect(() => {
    if (!isDirtyRef.current) return
    const timer = setTimeout(() => { autosaveCallbackRef.current() }, 3000)
    return () => clearTimeout(timer)
  }, [rating, comment])

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
    try {
      if (existingReview) {
        await updateReview.mutateAsync({
          reviewId: existingReview.id,
          data: { rating: rating ?? undefined, comment: comment || undefined, is_draft: true },
        })
      } else {
        await submitReview.mutateAsync({ rating: rating ?? undefined, comment: comment || undefined, is_draft: true })
      }
      notifications.show({ color: 'teal', message: 'Draft saved' })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not save draft'
      notifications.show({ color: 'red', message })
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
    <Stack gap="md">
      <Text size="sm" fw={600}>{title}</Text>
      <div>
        <Group justify="space-between" mb={4}>
          <Text size="sm">Rating</Text>
          <Text size="sm" fw={500} c="violet">
            {rating !== null ? `${rating} / 10` : '—'}
          </Text>
        </Group>
        <Slider
          min={0}
          max={10}
          step={0.1}
          value={rating ?? 0}
          onChange={(v) => { isDirtyRef.current = true; setRating(v) }}
          marks={[0, 2, 4, 6, 8, 10].map((v) => ({ value: v, label: String(v) }))}
          mb="lg"
        />
      </div>
      <Textarea
        label="Comment (optional)"
        placeholder="What did you think?"
        value={comment}
        onChange={(e) => { isDirtyRef.current = true; setComment(e.currentTarget.value) }}
        maxLength={1000}
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
        {!isPublished && autosavedAt && (
          <Text size="xs" c="dimmed">
            Autosaved {autosavedAt.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
          </Text>
        )}
      </Group>
    </Stack>
  )
}
