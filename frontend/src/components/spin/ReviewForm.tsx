import { useEffect, useState } from 'react'
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

  const [rating, setRating] = useState<number | null>(existingReview?.rating ?? null)
  const [comment, setComment] = useState(existingReview?.comment ?? '')
  const submitReview = useSubmitReview(albumId)
  const updateReview = useUpdateReview(albumId)

  useEffect(() => {
    if (isDraft && existingReview) {
      setRating(existingReview.rating)
      setComment(existingReview.comment ?? '')
    }
  }, [existingReview?.id])

  if (existingReview && !isDraft) {
    return (
      <Stack gap="xs">
        <Text size="sm" fw={600}>Your review</Text>
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
      if (isDraft && existingReview) {
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
      if (isDraft && existingReview) {
        await updateReview.mutateAsync({
          reviewId: existingReview.id,
          data: { rating: rating ?? undefined, comment: comment || undefined, is_draft: false },
        })
      } else {
        await submitReview.mutateAsync({ rating: rating ?? undefined, comment: comment || undefined })
      }
      notifications.show({ color: 'green', message: 'Review submitted' })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not submit review'
      notifications.show({ color: 'red', message })
    }
  }

  const isLoading = submitReview.isPending || updateReview.isPending

  return (
    <Stack gap="md">
      <Text size="sm" fw={600}>{isDraft ? 'Your draft review' : 'Your review'}</Text>
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
          onChange={setRating}
          marks={[0, 2, 4, 6, 8, 10].map((v) => ({ value: v, label: String(v) }))}
          mb="lg"
        />
      </div>
      <Textarea
        label="Comment (optional)"
        placeholder="What did you think?"
        value={comment}
        onChange={(e) => setComment(e.currentTarget.value)}
        maxLength={1000}
        autosize
        minRows={2}
      />
      <Group gap="xs">
        <Button variant="default" onClick={handleSaveDraft} loading={isLoading}>
          Save draft
        </Button>
        <Button onClick={handleSubmit} loading={isLoading} disabled={rating === null}>
          Submit review
        </Button>
      </Group>
    </Stack>
  )
}
