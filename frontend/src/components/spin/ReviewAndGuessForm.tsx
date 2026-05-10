import { useEffect, useState } from 'react'
import {
  ActionIcon,
  Alert,
  Avatar,
  Button,
  Group,
  Modal,
  Skeleton,
  Slider,
  Stack,
  Text,
  Textarea,
  Tooltip,
} from '@mantine/core'
import { IconPencil, IconStar, IconX } from '@tabler/icons-react'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useMyReview, useMyGuess, useSubmitReview, useUpdateReview, useCheckGuess, useGuessOptions } from '../../hooks/useDailySpin'
import { useAuth } from '../../hooks/useAuth'
import { ApiError } from '../../services/apiClient'
import GuessResult from './GuessResult'
import type { ReviewResponse } from '../../types/album'

interface Props {
  albumId: number
  groupId: number
  groupAlbumId: number
  addedBy: number | null
  allowGuessing?: boolean
}

// ==================== AVATAR SELECTOR ====================

type GuessSelection = number | 'chaos' | null

interface AvatarSelectorProps {
  groupId: number
  groupAlbumId: number
  selected: GuessSelection
  onChange: (selection: GuessSelection) => void
}

function AvatarSelector({ groupId, groupAlbumId, selected, onChange }: AvatarSelectorProps) {
  const { user } = useAuth()
  const { data: optionsData } = useGuessOptions(groupId, groupAlbumId)
  const eligible = optionsData?.options.filter((o) => o.user_id !== user?.id) ?? []
  const hasChaosOption = optionsData?.has_chaos_option ?? false

  return (
    <Group gap="xs">
      {eligible.map((o) => {
        const isSelected = selected === o.user_id
        return (
          <Tooltip
            key={o.user_id}
            label={o.display_name ? `${o.display_name} (${o.username})` : o.username}
            withArrow
          >
            <Avatar
              size="md"
              radius="xl"
              color="violet"
              variant={isSelected ? 'filled' : 'light'}
              style={{
                cursor: 'pointer',
                outline: isSelected ? '2px solid var(--mantine-color-violet-5)' : 'none',
                outlineOffset: 2,
              }}
              onClick={() => onChange(isSelected ? null : o.user_id)}
            >
              {o.username[0].toUpperCase()}
            </Avatar>
          </Tooltip>
        )
      })}
      {hasChaosOption && (
        <Tooltip label="Outside the group — random pick" withArrow>
          <Avatar
            size="md"
            radius="xl"
            color="gray"
            variant={selected === 'chaos' ? 'filled' : 'light'}
            style={{
              cursor: 'pointer',
              outline: selected === 'chaos' ? '2px solid var(--mantine-color-gray-5)' : 'none',
              outlineOffset: 2,
            }}
            onClick={() => onChange(selected === 'chaos' ? null : 'chaos')}
          >
            ?
          </Avatar>
        </Tooltip>
      )}
    </Group>
  )
}

// ==================== REVIEW SUMMARY ====================

function ReviewSummary({ review }: { review: ReviewResponse }) {
  return (
    <Stack gap="xs">
      <Text size="sm" fw={600}>Your review</Text>
      <Group gap="xs">
        <Text size="sm" c="dimmed">Rating:</Text>
        <Text size="sm" fw={500}>{review.rating !== null ? `${review.rating} / 10` : '—'}</Text>
      </Group>
      {review.comment && (
        <Text size="sm" c="dimmed" fs="italic">&ldquo;{review.comment}&rdquo;</Text>
      )}
    </Stack>
  )
}

// ==================== MAIN COMPONENT ====================

export default function ReviewAndGuessForm({ albumId, groupId, groupAlbumId, addedBy, allowGuessing = true }: Props) {
  const { user } = useAuth()
  const { data: existingReview, isLoading: reviewLoading } = useMyReview(albumId)
  const { data: existingGuess, isLoading: guessLoading } = useMyGuess(groupId, groupAlbumId)

  const isSelfNominated = user?.id === addedBy
  const isDraft = !!existingReview?.is_draft
  const hasPublishedReview = existingReview && !existingReview.is_draft ? existingReview : null

  const submitReview = useSubmitReview(albumId)
  const updateReview = useUpdateReview(albumId)
  const checkGuess = useCheckGuess(groupId, groupAlbumId)

  const [rating, setRating] = useState<number | null>(null)
  const [comment, setComment] = useState('')
  const [guessedUserId, setGuessedUserId] = useState<GuessSelection>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [editRating, setEditRating] = useState(0)
  const [editComment, setEditComment] = useState('')
  const [confirmOpen, { open: openConfirm, close: closeConfirm }] = useDisclosure(false)

  // Pre-fill form state when a draft exists (data may arrive asynchronously)
  useEffect(() => {
    if (isDraft && existingReview) {
      setRating(existingReview.rating)
      setComment(existingReview.comment ?? '')
    }
  }, [existingReview?.id])

  const isPending = submitReview.isPending || checkGuess.isPending || updateReview.isPending

  const startEditing = (r: ReviewResponse) => {
    setEditRating(r.rating ?? 0)
    setEditComment(r.comment ?? '')
    setIsEditing(true)
  }

  const handleUpdate = async (r: ReviewResponse) => {
    try {
      await updateReview.mutateAsync({
        reviewId: r.id,
        data: { rating: editRating, comment: editComment || undefined },
      })
      setIsEditing(false)
      notifications.show({ color: 'green', message: 'Review updated' })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not update review'
      notifications.show({ color: 'red', message })
    }
  }

  if (reviewLoading || guessLoading) return <Skeleton h={80} />

  const selfNominatedBanner = (
    <Alert icon={<IconStar size={16} />} color="violet" variant="light">
      You nominated this album.
    </Alert>
  )

  // ── Edit mode (published review) ─────────────────────────────────────────
  if (hasPublishedReview && isEditing) {
    return (
      <Stack gap="md">
        <Group justify="space-between" align="center">
          <Text size="sm" fw={600}>Edit your review</Text>
          <ActionIcon variant="subtle" size="sm" onClick={() => setIsEditing(false)}>
            <IconX size={14} />
          </ActionIcon>
        </Group>
        <div>
          <Group justify="space-between" mb={4}>
            <Text size="sm">Rating</Text>
            <Text size="sm" fw={500} c="violet">{editRating} / 10</Text>
          </Group>
          <Slider
            min={0} max={10} step={0.1}
            value={editRating} onChange={setEditRating}
            marks={[0, 2, 4, 6, 8, 10].map((v) => ({ value: v, label: String(v) }))}
            mb="lg"
          />
        </div>
        <Textarea
          label="Comment (optional)"
          value={editComment}
          onChange={(e) => setEditComment(e.currentTarget.value)}
          maxLength={1000}
          autosize
          minRows={2}
        />
        <Group gap="xs">
          <Button loading={updateReview.isPending} onClick={() => handleUpdate(hasPublishedReview)}>
            Save
          </Button>
          <Button variant="default" onClick={() => setIsEditing(false)}>
            Cancel
          </Button>
        </Group>
      </Stack>
    )
  }

  // ── Published review (guessing disabled) ─────────────────────────────────
  if (hasPublishedReview && !allowGuessing) {
    return (
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <ReviewSummary review={hasPublishedReview} />
          <ActionIcon variant="subtle" size="sm" onClick={() => startEditing(hasPublishedReview)}>
            <IconPencil size={14} />
          </ActionIcon>
        </Group>
      </Stack>
    )
  }

  // ── Published review + already guessed (or self-nominated) ───────────────
  if (hasPublishedReview && (existingGuess || isSelfNominated)) {
    return (
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <ReviewSummary review={hasPublishedReview} />
          <ActionIcon variant="subtle" size="sm" onClick={() => startEditing(hasPublishedReview)}>
            <IconPencil size={14} />
          </ActionIcon>
        </Group>
        {isSelfNominated ? selfNominatedBanner : <GuessResult result={existingGuess!} />}
      </Stack>
    )
  }

  // ── Published review, no guess yet ───────────────────────────────────────
  if (hasPublishedReview) {
    const handleGuessSubmit = async () => {
      if (guessedUserId === null) return
      try {
        await checkGuess.mutateAsync({ guessed_user_id: guessedUserId === 'chaos' ? null : guessedUserId })
      } catch (err) {
        const message = err instanceof ApiError ? err.message : 'Could not submit guess'
        notifications.show({ color: 'red', message })
      }
    }

    return (
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <ReviewSummary review={hasPublishedReview} />
          <ActionIcon variant="subtle" size="sm" onClick={() => startEditing(hasPublishedReview)}>
            <IconPencil size={14} />
          </ActionIcon>
        </Group>
        <Stack gap="xs">
          <Text size="sm" fw={600}>Who nominated this album?</Text>
          <AvatarSelector groupId={groupId} groupAlbumId={groupAlbumId} selected={guessedUserId} onChange={setGuessedUserId} />
          <Button
            variant="light"
            style={{ alignSelf: 'flex-start' }}
            disabled={guessedUserId === null}
            loading={checkGuess.isPending}
            onClick={handleGuessSubmit}
          >
            Submit guess
          </Button>
        </Stack>
      </Stack>
    )
  }

  // ── No review yet / Draft ─────────────────────────────────────────────────
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

  const doSubmit = async (skipGuess: boolean) => {
    if (rating === null) {
      notifications.show({ color: 'red', message: 'Please set a rating' })
      return
    }
    closeConfirm()
    try {
      if (isDraft && existingReview) {
        await updateReview.mutateAsync({
          reviewId: existingReview.id,
          data: { rating: rating ?? undefined, comment: comment || undefined, is_draft: false },
        })
      } else {
        await submitReview.mutateAsync({ rating: rating ?? undefined, comment: comment || undefined })
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not submit review'
      notifications.show({ color: 'red', message })
      return
    }

    if (!skipGuess && guessedUserId !== null) {
      try {
        await checkGuess.mutateAsync({ guessed_user_id: guessedUserId === 'chaos' ? null : guessedUserId })
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.message
            : 'Review saved, but guess could not be submitted'
        notifications.show({ color: 'yellow', message })
        return
      }
    }

    notifications.show({ color: 'green', message: 'Review submitted' })
  }

  const handleSubmitClick = () => {
    if (rating === null) {
      notifications.show({ color: 'red', message: 'Please set a rating' })
      return
    }
    if (!allowGuessing || isSelfNominated || guessedUserId) {
      doSubmit(!allowGuessing)
    } else {
      openConfirm()
    }
  }

  return (
    <>
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
        {allowGuessing && (isSelfNominated ? (
          selfNominatedBanner
        ) : (
          <Stack gap="xs">
            <Text size="sm">Who nominated this? (optional)</Text>
            <AvatarSelector groupId={groupId} groupAlbumId={groupAlbumId} selected={guessedUserId} onChange={setGuessedUserId} />
          </Stack>
        ))}
        <Group gap="xs">
          <Button variant="default" onClick={handleSaveDraft} loading={isPending}>
            Save draft
          </Button>
          <Button onClick={handleSubmitClick} loading={isPending} disabled={rating === null}>
            Submit review
          </Button>
        </Group>
      </Stack>

      {allowGuessing && (
        <Modal opened={confirmOpen} onClose={closeConfirm} title="Submit without a guess?">
          <Text size="sm" mb="lg">
            You haven&apos;t selected who nominated this album. Submit your review without a guess?
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={closeConfirm}>
              Go back
            </Button>
            <Button loading={isPending} onClick={() => doSubmit(true)}>
              Submit anyway
            </Button>
          </Group>
        </Modal>
      )}
    </>
  )
}
