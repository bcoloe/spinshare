import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/renderWithProviders'
import ReviewHistory from './ReviewHistory'
import type { CheckGuessResponse, GroupAlbumResponse, ReviewResponse } from '../../types/album'
import type { GroupMemberResponse } from '../../types/group'

const VIEWER_ID = 1

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ user: { id: VIEWER_ID } }),
}))

vi.mock('../../hooks/useDailySpin', () => ({
  useCheckGuess: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useGuessOptions: () => ({ data: undefined, isLoading: false }),
  useUpdateReview: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('../../context/UnseenReviewsContext', () => ({
  useUnseenReviews: () => ({ isUnseen: () => false, markSeen: vi.fn() }),
}))

const mockGetMyReviews = vi.fn()
const mockGetMyGuesses = vi.fn()
vi.mock('../../services/albumService', () => ({
  albumService: {
    getMyReviewsForGroup: () => mockGetMyReviews(),
    getMyGuessesForGroup: () => mockGetMyGuesses(),
    getAllReviews: () => Promise.resolve([]),
  },
}))

vi.mock('../../services/statsService', () => ({
  statsService: { getAlbumGuessStats: () => Promise.resolve(undefined) },
}))

const MEMBERS: GroupMemberResponse[] = [
  { user_id: VIEWER_ID, username: 'viewer' },
  { user_id: 2, username: 'kate' },
  { user_id: 3, username: 'alex' },
  { user_id: 4, username: 'sam' },
].map((m) => ({
  ...m,
  role: 'member',
  joined_at: '2026-01-01T00:00:00Z',
  first_name: null,
  last_name: null,
  name_is_public: false,
}))

function groupAlbum(id: number, title: string, nominators: number[]): GroupAlbumResponse {
  return {
    id,
    group_id: 1,
    album_id: id * 10,
    added_by: nominators[0],
    status: 'reviewed',
    added_at: '2026-01-01T00:00:00Z',
    selected_date: '2026-01-02T00:00:00Z',
    dealt_at: null,
    album: {
      id: id * 10,
      spotify_album_id: null,
      apple_music_album_id: null,
      youtube_music_id: null,
      artist_url: null,
      wikipedia_url: null,
      title,
      artist: 'Artist',
      release_date: null,
      cover_url: null,
      added_at: '2026-01-01T00:00:00Z',
      genres: [],
    },
    nomination_count: nominators.length,
    nominator_user_ids: nominators,
    avg_rating: 7,
    review_count: 1,
  }
}

function review(ga: GroupAlbumResponse): ReviewResponse {
  return {
    id: ga.id,
    album_id: ga.album_id,
    user_id: VIEWER_ID,
    rating: 8,
    comment: null,
    is_draft: false,
    reviewed_at: '2026-01-03T00:00:00Z',
    updated_at: null,
    is_first_review: false,
  }
}

function guess(ga: GroupAlbumResponse): CheckGuessResponse {
  return {
    guess: {
      id: ga.id,
      group_album_id: ga.id,
      guessing_user_id: VIEWER_ID,
      guessed_user_id: 2,
      correct: true,
      created_at: '2026-01-03T00:00:00Z',
    },
    correct: true,
    nominator_user_ids: ga.nominator_user_ids,
    nominator_usernames: [],
    is_chaos_selection: false,
    guessed_username: 'kate',
  }
}

// kate + alex co-nominated the guessed album; sam alone nominated the unguessed one
const GUESSED = groupAlbum(1, 'Guessed Album', [2, 3])
const UNGUESSED = groupAlbum(2, 'Unguessed Album', [4])

function renderHistory(allowGuessing = true) {
  return renderWithProviders(
    <ReviewHistory
      groupId={1}
      albums={[GUESSED, UNGUESSED]}
      members={MEMBERS}
      isLoading={false}
      allowGuessing={allowGuessing}
    />,
  )
}

describe('ReviewHistory nominators', () => {
  beforeEach(() => {
    mockGetMyReviews.mockResolvedValue([review(GUESSED), review(UNGUESSED)])
    mockGetMyGuesses.mockResolvedValue([guess(GUESSED)])
  })

  it('reveals co-nominators only on albums the viewer has guessed', async () => {
    renderHistory()
    expect(await screen.findByRole('button', { name: 'Nominated by alex, kate' })).toBeInTheDocument()
    expect(screen.getByText('Guess?')).toBeInTheDocument()
    expect(screen.queryByText('sam')).not.toBeInTheDocument()
  })

  it('matches the filter on revealed nominators', async () => {
    renderHistory()
    await userEvent.type(await screen.findByPlaceholderText(/nominator/), 'kate')
    expect(screen.getByText('Guessed Album')).toBeInTheDocument()
    expect(screen.queryByText('Unguessed Album')).not.toBeInTheDocument()
  })

  it('never matches the filter on nominators of an unguessed album', async () => {
    renderHistory()
    await userEvent.type(await screen.findByPlaceholderText(/nominator/), 'sam')
    expect(screen.queryByText('Unguessed Album')).not.toBeInTheDocument()
    expect(screen.queryByText('Guessed Album')).not.toBeInTheDocument()
  })

  it('reveals every album’s nominators when guessing is off', async () => {
    renderHistory(false)
    expect(await screen.findByText('sam')).toBeInTheDocument()
    await userEvent.type(screen.getByPlaceholderText(/nominator/), 'sam')
    expect(screen.getByText('Unguessed Album')).toBeInTheDocument()
  })
})
