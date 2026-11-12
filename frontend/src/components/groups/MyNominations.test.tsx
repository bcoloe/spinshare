import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/renderWithProviders'
import MyNominations from './MyNominations'
import type { GroupAlbumResponse } from '../../types/album'

const USER_ID = 2

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({ user: { id: USER_ID }, isInitializing: false }),
}))

vi.mock('../../hooks/useGroups', () => ({
  useGroup: () => ({ data: { current_user_role: 'member', is_global: false, settings: {} } }),
}))

const mockUseGroupAlbums = vi.fn()
vi.mock('../../hooks/useAlbums', () => ({
  useGroupAlbums: () => mockUseGroupAlbums(),
  useNominationCount: () => ({ data: { today_count: 0 } }),
  useRemoveGroupAlbum: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('../albums/AlbumSearchModal', () => ({ default: () => null }))

function nomination(
  id: number,
  title: string,
  status: GroupAlbumResponse['status'],
  nominators: number[] = [USER_ID],
): GroupAlbumResponse {
  return {
    id,
    group_id: 1,
    album_id: id * 10,
    added_by: nominators[0],
    status,
    added_at: '2026-01-01T00:00:00Z',
    selected_date: null,
    dealt_at: null,
    album: {
      id: id * 10,
      title,
      artist: `Artist ${id}`,
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
  nomination(1, 'Pending One', 'pending'),
  nomination(2, 'Pending Two', 'pending'),
  nomination(3, 'Reviewed One', 'reviewed'),
  nomination(4, 'Someone Else', 'pending', [99]),
]

function renderList() {
  mockUseGroupAlbums.mockReturnValue({ data: ALBUMS, isLoading: false })
  return renderWithProviders(<MyNominations groupId={1} />)
}

describe('MyNominations status filter', () => {
  it('shows counts of the caller’s own nominations per status', () => {
    renderList()
    expect(screen.getByText('All (3)')).toBeInTheDocument()
    expect(screen.getByText('Pending (2)')).toBeInTheDocument()
    expect(screen.getByText('Selected (0)')).toBeInTheDocument()
    expect(screen.getByText('Reviewed (1)')).toBeInTheDocument()
  })

  it('narrows the list to the chosen status', async () => {
    const user = userEvent.setup()
    renderList()
    await user.click(screen.getByText('Reviewed (1)'))

    expect(screen.getByText('Reviewed One')).toBeInTheDocument()
    expect(screen.queryByText('Pending One')).not.toBeInTheDocument()
    expect(screen.queryByText('Pending Two')).not.toBeInTheDocument()
  })

  it('combines the status filter with the text filter', async () => {
    const user = userEvent.setup()
    renderList()
    await user.click(screen.getByText('Pending (2)'))
    await user.type(screen.getByPlaceholderText(/filter by album or artist/i), 'two')

    expect(screen.getByText('Pending Two')).toBeInTheDocument()
    expect(screen.queryByText('Pending One')).not.toBeInTheDocument()
  })

  it('says so when no nomination has the chosen status', async () => {
    const user = userEvent.setup()
    renderList()
    await user.click(screen.getByText('Selected (0)'))
    expect(screen.getByText('No nominations match your filter.')).toBeInTheDocument()
  })
})
