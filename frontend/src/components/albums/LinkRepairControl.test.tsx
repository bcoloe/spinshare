import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../../test/renderWithProviders'
import LinkRepairControl from './LinkRepairControl'
import type { AlbumResponse } from '../../types/album'

const mockUseAuth = vi.fn()
vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}))

const ALBUM: AlbumResponse = {
  id: 7,
  title: 'OK Computer',
  artist: 'Radiohead',
  spotify_album_id: 'someSpotifyId',
  apple_music_album_id: null,
  youtube_music_id: null,
  artist_url: null,
  wikipedia_url: null,
  release_date: '1997-05',
  cover_url: null,
  added_at: '2026-01-01T00:00:00Z',
  genres: [],
}

function renderControl(user: unknown) {
  mockUseAuth.mockReturnValue({ user, isInitializing: false })
  return renderWithProviders(<LinkRepairControl album={ALBUM} />)
}

describe('LinkRepairControl', () => {
  it('offers admins the link editor', () => {
    renderControl({ id: 1, username: 'admin', is_admin: true })
    expect(screen.getByRole('button', { name: /edit links/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /report link issue/i })).not.toBeInTheDocument()
  })

  it('offers ordinary members the report flow', () => {
    renderControl({ id: 2, username: 'member', is_admin: false })
    expect(screen.getByRole('button', { name: /report link issue/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /edit links/i })).not.toBeInTheDocument()
  })

  it('offers signed-out visitors nothing — reporting needs an account', () => {
    renderControl(null)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
