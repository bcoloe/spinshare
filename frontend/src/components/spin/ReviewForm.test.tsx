import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/renderWithProviders'
import ReviewForm from './ReviewForm'
import type { ReviewResponse } from '../../types/album'

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ user: { id: 7 } }),
}))

const mockUpdateReview = vi.fn()
const mockSubmitReview = vi.fn()
vi.mock('../../services/albumService', () => ({
  albumService: {
    updateReview: (...args: unknown[]) => mockUpdateReview(...args),
    submitReview: (...args: unknown[]) => mockSubmitReview(...args),
  },
}))

const ALBUM = 42

function draft(overrides: Partial<ReviewResponse> = {}): ReviewResponse {
  return {
    id: 5,
    album_id: ALBUM,
    user_id: 7,
    rating: 6,
    comment: 'server copy',
    is_draft: true,
    reviewed_at: '2026-10-12T10:00:00Z',
    updated_at: null,
    ...overrides,
  } as ReviewResponse
}

beforeEach(() => {
  localStorage.clear()
  mockUpdateReview.mockReset()
  mockSubmitReview.mockReset()
})

describe('ReviewForm', () => {
  it('Submit stays clickable while a draft save is in flight, and publishes that draft (#186)', async () => {
    const user = userEvent.setup()
    let finishSave: (r: ReviewResponse) => void = () => {}
    mockUpdateReview
      .mockImplementationOnce(() => new Promise((resolve) => { finishSave = resolve }))
      .mockImplementationOnce(async (_album, id, data) => draft({ id, ...data }))
    renderWithProviders(<ReviewForm albumId={ALBUM} existingReview={draft()} />)

    fireEvent.keyDown(screen.getByRole('slider'), { key: 'ArrowRight' }) // 6 → 6.1
    await user.click(screen.getByRole('button', { name: 'Save draft' }))
    await waitFor(() => expect(mockUpdateReview).toHaveBeenCalledTimes(1))

    const submit = screen.getByRole('button', { name: 'Submit review' })
    expect(submit).toBeEnabled()
    await user.click(submit)
    expect(mockUpdateReview).toHaveBeenCalledTimes(1) // publishing waits for the save

    await act(async () => finishSave(draft({ rating: 6.1, updated_at: '2026-10-12T12:00:00Z' })))

    await waitFor(() => expect(mockUpdateReview).toHaveBeenCalledTimes(2))
    expect(mockUpdateReview.mock.calls[1].slice(1, 3)).toEqual([5, { rating: 6.1, comment: 'server copy', is_draft: false }])
    expect(mockSubmitReview).not.toHaveBeenCalled()
  })
})
