import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/renderWithProviders'
import EditLinksModal from './EditLinksModal'
import { albumService } from '../../services/albumService'
import type { AlbumResponse } from '../../types/album'

vi.mock('../../services/albumService', () => ({
  albumService: { updateLinks: vi.fn() },
}))

const ALBUM: AlbumResponse = {
  id: 7,
  title: 'OK Computer',
  artist: 'Radiohead',
  spotify_album_id: '3v1nspBDZhlcJGDW6fUJQR',
  apple_music_album_id: null,
  youtube_music_id: null,
  artist_url: null,
  wikipedia_url: 'https://en.wikipedia.org/wiki/OK_Computer',
  release_date: '1997-05',
  cover_url: null,
  added_at: '2026-01-01T00:00:00Z',
  genres: [],
}

function renderModal(props: Partial<Parameters<typeof EditLinksModal>[0]> = {}) {
  const onClose = vi.fn()
  const utils = renderWithProviders(
    <EditLinksModal opened onClose={onClose} album={ALBUM} {...props} />,
  )
  return { ...utils, onClose }
}

describe('EditLinksModal', () => {
  beforeEach(() => {
    vi.mocked(albumService.updateLinks).mockReset()
    vi.mocked(albumService.updateLinks).mockResolvedValue({} as never)
  })

  describe('preview links', () => {
    it('builds a preview URL from the stored bare ID', () => {
      renderModal()
      const preview = screen.getByLabelText('Preview Spotify album link or ID')
      expect(preview).toHaveAttribute(
        'href',
        'https://open.spotify.com/album/3v1nspBDZhlcJGDW6fUJQR',
      )
      expect(preview).toHaveAttribute('target', '_blank')
    })

    it('previews a suggested value rather than the saved one', () => {
      renderModal({
        initialOverrides: { spotify_album_id: 'SUGGESTEDID123' },
        highlightField: 'spotify_album_id',
        highlightNote: 'Suggested by alice',
      })

      expect(screen.getByLabelText('Preview Spotify album link or ID')).toHaveAttribute(
        'href',
        'https://open.spotify.com/album/SUGGESTEDID123',
      )
      expect(screen.getByText('Suggested by alice')).toBeInTheDocument()
    })

    it('tracks what the admin types rather than the value it opened with', async () => {
      const user = userEvent.setup()
      renderModal()
      const input = screen.getByLabelText('Spotify album link or ID')

      await user.clear(input)
      await user.type(input, 'editedId999')

      await waitFor(() =>
        expect(screen.getByLabelText('Preview Spotify album link or ID')).toHaveAttribute(
          'href',
          'https://open.spotify.com/album/editedId999',
        ),
      )
    })

    it('has no href for a link the album does not have', () => {
      renderModal()
      expect(
        screen.getByLabelText('Preview Apple Music album link or ID'),
      ).not.toHaveAttribute('href')
    })
  })

  describe('showing the previous value', () => {
    it('shows what a suggestion would replace, struck through', () => {
      renderModal({
        initialOverrides: { spotify_album_id: 'SUGGESTEDID123' },
        highlightField: 'spotify_album_id',
      })

      const previous = screen.getByLabelText('Preview previous Spotify album link or ID')
      expect(previous).toHaveTextContent('3v1nspBDZhlcJGDW6fUJQR')
      expect(previous).toHaveAttribute(
        'href',
        'https://open.spotify.com/album/3v1nspBDZhlcJGDW6fUJQR',
      )
      expect(previous).toHaveStyle({ textDecoration: 'line-through' })
    })

    it('says nothing about fields that are unchanged', () => {
      renderModal()
      expect(screen.queryByText('Was')).not.toBeInTheDocument()
    })

    it('reports a previously empty link as empty rather than blank', async () => {
      const user = userEvent.setup()
      renderModal()

      await user.type(screen.getByLabelText('Apple Music album link or ID'), '123456')

      expect(await screen.findByText('empty')).toBeInTheDocument()
    })

    it('appears once the admin edits a field by hand', async () => {
      const user = userEvent.setup()
      renderModal()

      await user.type(screen.getByLabelText('Spotify album link or ID'), 'XYZ')

      expect(await screen.findByText('Was')).toBeInTheDocument()
    })

    it('shows the previous value after the link is removed', async () => {
      const user = userEvent.setup()
      renderModal()

      await user.click(screen.getByLabelText('Remove Spotify album link or ID'))

      expect(
        await screen.findByLabelText('Preview previous Spotify album link or ID'),
      ).toHaveTextContent('3v1nspBDZhlcJGDW6fUJQR')
    })

    it('restores the original value when revert is clicked', async () => {
      const user = userEvent.setup()
      renderModal({
        initialOverrides: { spotify_album_id: 'SUGGESTEDID123' },
        highlightField: 'spotify_album_id',
      })
      const input = screen.getByLabelText('Spotify album link or ID') as HTMLInputElement
      expect(input.value).toBe('SUGGESTEDID123')

      await user.click(screen.getByRole('button', { name: 'Revert' }))

      expect(input.value).toBe('3v1nspBDZhlcJGDW6fUJQR')
      expect(screen.queryByText('Was')).not.toBeInTheDocument()
    })
  })

  describe('removing a link', () => {
    it('clears the field when the remove button is clicked', async () => {
      const user = userEvent.setup()
      renderModal()
      const input = screen.getByLabelText('Spotify album link or ID') as HTMLInputElement
      expect(input.value).toBe('3v1nspBDZhlcJGDW6fUJQR')

      await user.click(screen.getByLabelText('Remove Spotify album link or ID'))

      expect(input.value).toBe('')
    })

    it('sends an explicit null for the cleared link on save', async () => {
      const user = userEvent.setup()
      renderModal()

      await user.click(screen.getByLabelText('Remove Spotify album link or ID'))
      await user.click(screen.getByRole('button', { name: /^save$/i }))

      await waitFor(() =>
        expect(albumService.updateLinks).toHaveBeenCalledWith(
          7,
          expect.objectContaining({
            spotify_album_id: null,
            // Untouched links keep their values.
            wikipedia_url: 'https://en.wikipedia.org/wiki/OK_Computer',
          }),
        ),
      )
    })

    it('disables remove for a link that is already absent', () => {
      renderModal()
      expect(screen.getByLabelText('Remove Apple Music album link or ID')).toBeDisabled()
    })

    it('tells the admin how removal works', () => {
      renderModal()
      expect(screen.getByText(/clear a field and save to remove/i)).toBeInTheDocument()
    })
  })

  it('passes a pasted share URL through for the server to normalise', async () => {
    const user = userEvent.setup()
    renderModal()
    const url = 'https://open.spotify.com/intl-de/album/abc123?si=xyz'
    const input = screen.getByLabelText('Spotify album link or ID')

    await user.clear(input)
    await user.type(input, url)
    await user.click(screen.getByRole('button', { name: /^save$/i }))

    await waitFor(() =>
      expect(vi.mocked(albumService.updateLinks).mock.calls[0][1].spotify_album_id).toBe(url),
    )
  })
})
