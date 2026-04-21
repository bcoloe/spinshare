import { useState } from 'react'
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
import { useMyReview, useMyGuess, useSubmitReview, useUpdateReview, useCheckGuess } from '../../hooks/useDailySpin'
import { useGroupMembers } from '../../hooks/useGroups'
import { useAuth } from '../../hooks/useAuth'
import { ApiError } from '../../services/apiClient'
import GuessResult from './GuessResult'
import type { ReviewResponse } from '../../types/album'

interface Props {
  albumId: number
  groupId: number
  groupAlbumId: number
  addedBy: number
}

// ==================== AVATAR SELECTOR ====================

interface AvatarSelectorProps {
  groupId: number
  selected: number | null
  onChange: (userId: number | null) => void
}

function AvatarSelector({ groupId, selected, onChange }: AvatarSelectorProps) {
  const { user } = useAuth()
  const { data: members } = useGroupMembers(groupId)
  const eligible = members?.filter((m) => m.user_id !== user?.id) ?? []

  return (
    <Group gap="xs">
      {eligible.map((m) => {
        const isSelected = selected === m.user_id
        return (
          <Tooltip key={m.user_id} label={m.username} withArrow>
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
              onClick={() => onChange(isSelected ? null : m.user_id)}
            >
              {m.username[0].toUpperCase()}
            </Avatar>
          </Tooltip>
        )
      })}
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
        <Text size="sm" fw={500}>{review.rating} / 10</Text>
      </Group>
      {review.comment && (
        <Text size="sm" c="dimmed" fs="italic">&ldquo;{review.comment}&rdquo;</Text>
      )}
    </Stack>
  )
}

// ==================== MAIN COMPONENT ====================

export default function ReviewAndGuessForm({ albumId, groupId, groupAlbumId, addedBy }: Props) {
  const { user } = useAuth()
  const { data: existingReview, isLoading: reviewLoading } = useMyReview(albumId)
  const { data: existingGuess, isLoading: guessLoading } = useMyGuess(groupId, groupAlbumId)

  const isSelfNominated = user?.id === addedBy

  const submitReview = useSubmitReview(albumId)
  const updateReview = useUpdateReview(albumId)
  const checkGuess = useCheckGuess(groupId, groupAlbumId)

  const [rating, setRating] = useState<number | null>(null)
  const [comment, setComment] = useState('')
  const [guessedUserId, setGuessedUserId] = useState<number | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [editRating, setEditRating] = useState(0)
  const [editComment, setEditComment] = useState('')
  const [confirmOpen, { open: openConfirm, close: closeConfirm }] = useDisclosure(false)

  const isPending = submitReview.isPending || checkGuess.isPending

  const startEditing = (r: ReviewResponse) => {
    setEditRating(r.rating)
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

  // ── Edit mode (existing review) ──────────────────────────────────────────
  if (existingReview && isEditing) {
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
          <Button loading={updateReview.isPending} onClick={() => handleUpdate(existingReview)}>
            Save
          </Button>
          <Button variant="default" onClick={() => setIsEditing(false)}>
            Cancel
          </Button>
        </Group>
      </Stack>
    )
  }

  // ── Already reviewed + already guessed (or self-nominated) ───────────────
  if (existingReview && (existingGuess || isSelfNominated)) {
    return (
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <ReviewSummary review={existingReview} />
          <ActionIcon variant="subtle" size="sm" onClick={() => startEditing(existingReview)}>
            <IconPencil size={14} />
          </ActionIcon>
        </Group>
        {isSelfNominated ? selfNominatedBanner : <GuessResult result={existingGuess!} />}
      </Stack>
    )
  }

  // ── Already reviewed, no guess yet ──────────────────────────────────────
  if (existingReview) {
    const handleGuessSubmit = async () => {
      if (!guessedUserId) return
      try {
        await checkGuess.mutateAsync({ guessed_user_id: guessedUserId })
      } catch (err) {
        const message = err instanceof ApiError ? err.message : 'Could not submit guess'
        notifications.show({ color: 'red', message })
      }
    }

    return (
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <ReviewSummary review={existingReview} />
          <ActionIcon variant="subtle" size="sm" onClick={() => startEditing(existingReview)}>
            <IconPencil size={14} />
          </ActionIcon>
        </Group>
        <Stack gap="xs">
          <Text size="sm" fw={600}>Who nominated this album?</Text>
          <AvatarSelector groupId={groupId} selected={guessedUserId} onChange={setGuessedUserId} />
          <Button
            variant="light"
            style={{ alignSelf: 'flex-start' }}
            disabled={!guessedUserId}
            loading={checkGuess.isPending}
            onClick={handleGuessSubmit}
          >
            Submit guess
          </Button>
        </Stack>
      </Stack>
    )
  }

  // ── Not yet reviewed ─────────────────────────────────────────────────────
  const doSubmit = async (skipGuess: boolean) => {
    if (rating === null) {
      notifications.show({ color: 'red', message: 'Please set a rating' })
      return
    }
    closeConfirm()
    try {
      await submitReview.mutateAsync({ rating, comment: comment || undefined })
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not submit review'
      notifications.show({ color: 'red', message })
      return
    }

    if (!skipGuess && guessedUserId) {
      try {
        await checkGuess.mutateAsync({ guessed_user_id: guessedUserId })
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
    if (!isSelfNominated && !guessedUserId) {
      openConfirm()
    } else {
      doSubmit(false)
    }
  }

  return (
    <>
      <Stack gap="md">
        <Text size="sm" fw={600}>Your review</Text>
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
        {isSelfNominated ? (
          selfNominatedBanner
        ) : (
          <Stack gap="xs">
            <Text size="sm">Who nominated this? (optional)</Text>
            <AvatarSelector groupId={groupId} selected={guessedUserId} onChange={setGuessedUserId} />
          </Stack>
        )}
        <Button onClick={handleSubmitClick} loading={isPending} disabled={rating === null}>
          Submit review
        </Button>
      </Stack>

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
    </>
  )
}
