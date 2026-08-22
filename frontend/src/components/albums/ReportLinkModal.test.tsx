import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/renderWithProviders'
import ReportLinkModal from './ReportLinkModal'
import { linkReportService } from '../../services/linkReportService'
import type { AlbumResponse } from '../../types/album'

vi.mock('../../services/linkReportService', () => ({
  linkReportService: { submit: vi.fn() },
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

function renderModal() {
  const onClose = vi.fn()
  const utils = renderWithProviders(
    <ReportLinkModal opened onClose={onClose} album={ALBUM} />,
  )
  return { ...utils, onClose }
}

describe('ReportLinkModal', () => {
  beforeEach(() => {
    vi.mocked(linkReportService.submit).mockReset()
    vi.mocked(linkReportService.submit).mockResolvedValue({} as never)
  })

  it('shows the album being reported', () => {
    renderModal()
    expect(screen.getByText(/OK Computer — Radiohead/)).toBeInTheDocument()
  })

  it('offers the three reasons as radio options', () => {
    renderModal()
    expect(screen.getByRole('radio', { name: /Missing/ })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Wrong or broken/ })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Something else/ })).toBeInTheDocument()
  })

  it('submits with a reason code and no prose, needing only one click', async () => {
    const user = userEvent.setup()
    const { onClose } = renderModal()

    await user.click(screen.getByRole('radio', { name: /Missing/ }))
    await user.click(screen.getByRole('button', { name: /submit report/i }))

    await waitFor(() => expect(linkReportService.submit).toHaveBeenCalledWith(7, {
      link_field: 'spotify',
      reason_code: 'missing',
      reason_detail: null,
      suggested_url: null,
    }))
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('hides the free-text box until "other" is chosen', async () => {
    const user = userEvent.setup()
    renderModal()
    expect(screen.queryByLabelText(/tell us more/i)).not.toBeInTheDocument()

    await user.click(screen.getByRole('radio', { name: /Something else/ }))

    expect(await screen.findByLabelText(/tell us more/i)).toBeInTheDocument()
  })

  it('sends the detail typed under "other"', async () => {
    const user = userEvent.setup()
    renderModal()

    await user.click(screen.getByRole('radio', { name: /Something else/ }))
    await user.type(await screen.findByLabelText(/tell us more/i), 'Wrong regional edition.')
    await user.click(screen.getByRole('button', { name: /submit report/i }))

    await waitFor(() =>
      expect(vi.mocked(linkReportService.submit).mock.calls[0][1]).toMatchObject({
        reason_code: 'other',
        reason_detail: 'Wrong regional edition.',
      }),
    )
  })

  it('accepts "other" with no detail, since the box is optional', async () => {
    const user = userEvent.setup()
    renderModal()

    await user.click(screen.getByRole('radio', { name: /Something else/ }))
    await user.click(screen.getByRole('button', { name: /submit report/i }))

    await waitFor(() =>
      expect(vi.mocked(linkReportService.submit).mock.calls[0][1]).toMatchObject({
        reason_code: 'other',
        reason_detail: null,
      }),
    )
  })

  it('passes a pasted share URL straight through for the server to normalise', async () => {
    const user = userEvent.setup()
    renderModal()
    const url = 'https://open.spotify.com/album/3v1nspBDZhlcJGDW6fUJQR?si=abc'

    await user.type(screen.getByLabelText(/suggested replacement/i), url)
    await user.click(screen.getByRole('button', { name: /submit report/i }))

    await waitFor(() =>
      expect(vi.mocked(linkReportService.submit).mock.calls[0][1].suggested_url).toBe(url),
    )
  })

  it('annotates links the album does not currently have', async () => {
    const user = userEvent.setup()
    renderModal()

    await user.click(screen.getByRole('textbox', { name: /which link is wrong/i }))

    // Spotify is populated on ALBUM; Apple Music is not.
    expect(await screen.findByText('Apple Music (currently empty)')).toBeInTheDocument()
    expect(screen.getByText('Spotify')).toBeInTheDocument()
  })
})
