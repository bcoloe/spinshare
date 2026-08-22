import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/renderWithProviders'
import ParticipationMeter from './ParticipationMeter'
import type { GroupAlbumResponse } from '../../types/album'
import type { ParticipationResponse } from '../../types/group'

const mockUseAuth = vi.fn()
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}))

const mockUseParticipation = vi.fn()
const mockSetPriorityPick = vi.fn()
vi.mock('../../hooks/useGroups', () => ({
  useParticipation: () => mockUseParticipation(),
  useSetPriorityPick: () => ({ mutateAsync: mockSetPriorityPick, isPending: false }),
  useClearPriorityPick: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

const mockUseGroupAlbums = vi.fn()
vi.mock('../../hooks/useAlbums', () => ({
  useGroupAlbums: () => mockUseGroupAlbums(),
}))

const USER_ID = 2

function nomination(
  id: number,
  title: string,
  artist: string,
  nominators: number[] = [USER_ID],
): GroupAlbumResponse {
  return {
    id,
    group_id: 1,
    album_id: id * 10,
    added_by: nominators[0],
    status: 'pending',
    added_at: '2026-01-01T00:00:00Z',
    selected_date: null,
    dealt_at: null,
    album: {
      id: id * 10,
      title,
      artist,
      spotify_album_id: null,
      apple_music_album_id: null,
      youtube_music_id: null,
      artist_url: null,
      wikipedia_url: null,
      release_date: '2020',
      cover_url: null,
      added_at: '2026-01-01T00:00:00Z',
      genres: [],
    },
    nomination_count: nominators.length,
    nominator_user_ids: nominators,
    avg_rating: null,
    review_count: 0,
  }
}

const ALBUMS = [
  nomination(1, 'OK Computer', 'Radiohead'),
  nomination(2, 'Eat the Light', 'Lotus'),
  nomination(3, 'Kid A', 'Radiohead'),
]

function renderMeter(participation: Partial<ParticipationResponse> = {}) {
  mockUseAuth.mockReturnValue({ user: { id: USER_ID }, isInitializing: false })
  mockUseGroupAlbums.mockReturnValue({ data: ALBUMS })
  mockUseParticipation.mockReturnValue({
    data: {
      threshold: 3,
      credits: 3,
      can_pick: true,
      pending_pick: null,
      queue_position: null,
      queue_size: 0,
      ...participation,
    },
  })
  return renderWithProviders(<ParticipationMeter groupId={1} />)
}

describe('ParticipationMeter picker', () => {
  beforeEach(() => {
    mockSetPriorityPick.mockReset()
    mockSetPriorityPick.mockResolvedValue(undefined)
  })

  it('filters nominations by album title', async () => {
    const user = userEvent.setup()
    renderMeter()
    await user.click(screen.getByRole('button', { name: /choose priority album/i }))
    const filter = await screen.findByLabelText('Filter nominations')

    expect(await screen.findByText('Eat the Light')).toBeInTheDocument()
    await user.type(filter, 'kid a')

    expect(screen.getByText('Kid A')).toBeInTheDocument()
    expect(screen.queryByText('Eat the Light')).not.toBeInTheDocument()
    expect(screen.queryByText('OK Computer')).not.toBeInTheDocument()
  })

  it('filters by artist too, keeping every album by that artist', async () => {
    const user = userEvent.setup()
    renderMeter()
    await user.click(screen.getByRole('button', { name: /choose priority album/i }))
    const filter = await screen.findByLabelText('Filter nominations')
    await user.type(filter, 'radio')

    expect(screen.getByText('OK Computer')).toBeInTheDocument()
    expect(screen.getByText('Kid A')).toBeInTheDocument()
    expect(screen.queryByText('Eat the Light')).not.toBeInTheDocument()
  })

  it('says so when nothing matches', async () => {
    const user = userEvent.setup()
    renderMeter()
    await user.click(screen.getByRole('button', { name: /choose priority album/i }))
    const filter = await screen.findByLabelText('Filter nominations')
    await user.type(filter, 'zzz')

    expect(screen.getByText(/no nominations match/i)).toBeInTheDocument()
  })

  it('promotes the album that was clicked', async () => {
    const user = userEvent.setup()
    renderMeter()
    await user.click(screen.getByRole('button', { name: /choose priority album/i }))
    const filter = await screen.findByLabelText('Filter nominations')
    await user.type(filter, 'lotus')
    await user.click(screen.getByText('Eat the Light'))

    expect(mockSetPriorityPick).toHaveBeenCalledWith(2)
  })

  it('marks the queued pick current on a co-nominated album', async () => {
    const user = userEvent.setup()
    // The list carries the earliest nominator's row (id 2); the queued pick is the
    // caller's own row for the same album, so ids differ but the album matches.
    const queued = { ...nomination(2, 'Eat the Light', 'Lotus'), id: 99 }
    renderMeter({ can_pick: false, pending_pick: queued, queue_position: 1, queue_size: 1 })

    await user.click(screen.getByRole('button', { name: /change/i }))
    expect(await screen.findByText('Current')).toBeInTheDocument()
  })
})
