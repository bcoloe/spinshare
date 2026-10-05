import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/renderWithProviders'
import AlbumReviewsTable from './AlbumReviewsTable'
import type { AlbumReviewItem } from '../../types/album'

/** The SpoilerBlur wrapper around a node, present only while it is hidden. */
function blurWrapper(el: HTMLElement): HTMLElement | null {
  return el.closest('[aria-hidden="true"]')
}

function review(over: Partial<AlbumReviewItem> = {}): AlbumReviewItem {
  return {
    id: 1,
    album_id: 7,
    user_id: 1,
    username: 'kate',
    first_name: null,
    last_name: null,
    rating: 9.1,
    comment: 'A total knockout.',
    is_draft: false,
    reviewed_at: '2026-03-04T12:00:00Z',
    updated_at: null,
    ...over,
  }
}

const reviews = [
  review({ id: 1, username: 'kate', rating: 9.1, comment: 'A total knockout.', reviewed_at: '2026-03-04T12:00:00Z' }),
  review({ id: 2, username: 'alex', rating: 4.2, comment: 'Not for me.', reviewed_at: '2026-03-06T12:00:00Z' }),
]

describe('AlbumReviewsTable', () => {
  it('counts the reviews and lists their authors', () => {
    renderWithProviders(<AlbumReviewsTable reviews={reviews} loading={false} hidden={false} />)
    expect(screen.getByText('2 reviews')).toBeInTheDocument()
    expect(screen.getByText('kate')).toBeInTheDocument()
    expect(screen.getByText('alex')).toBeInTheDocument()
  })

  it('opens one review body at a time on a row click', async () => {
    renderWithProviders(<AlbumReviewsTable reviews={reviews} loading={false} hidden={false} />)

    await userEvent.click(screen.getByText('kate'))
    expect(screen.getByText('"A total knockout."')).toBeInTheDocument()

    await userEvent.click(screen.getByText('alex'))
    expect(screen.queryByText('"A total knockout."')).not.toBeInTheDocument()
    expect(screen.getByText('"Not for me."')).toBeInTheDocument()
  })

  it('blurs every rating while hidden', () => {
    renderWithProviders(
      <AlbumReviewsTable reviews={reviews} loading={false} hidden onToggleHidden={() => {}} />,
    )
    expect(blurWrapper(screen.getByText('9.1'))?.getAttribute('style')).toContain('blur(')
    expect(blurWrapper(screen.getByText('4.2'))?.getAttribute('style')).toContain('blur(')
  })

  it('blurs the reviewers too, so the scores stay unattributable', () => {
    renderWithProviders(
      <AlbumReviewsTable reviews={reviews} loading={false} hidden onToggleHidden={() => {}} />,
    )
    expect(blurWrapper(screen.getByText('kate'))?.getAttribute('style')).toContain('blur(')
    expect(blurWrapper(screen.getByText('alex'))?.getAttribute('style')).toContain('blur(')
  })

  it('strips the band colors off the ratings while hidden', () => {
    const { rerender } = renderWithProviders(
      <AlbumReviewsTable reviews={reviews} loading={false} hidden onToggleHidden={() => {}} />,
    )
    // 9.1 is violet and 4.2 orange — far enough apart to read straight through a blur.
    for (const rating of ['9.1', '4.2']) {
      const style = screen.getByText(rating).getAttribute('style') ?? ''
      expect(style).toContain('--mantine-color-gray-5')
    }

    rerender(
      <AlbumReviewsTable reviews={reviews} loading={false} hidden={false} onToggleHidden={() => {}} />,
    )
    expect(screen.getByText('9.1').getAttribute('style')).toContain('--mantine-color-violet-6')
    expect(screen.getByText('4.2').getAttribute('style')).toContain('--mantine-color-orange-6')
  })

  it('keeps the dates and the count in the clear while hidden', () => {
    renderWithProviders(
      <AlbumReviewsTable reviews={reviews} loading={false} hidden onToggleHidden={() => {}} />,
    )
    expect(blurWrapper(screen.getByText('Mar 4, 2026'))).toBeNull()
    expect(blurWrapper(screen.getByText('2 reviews'))).toBeNull()
  })

  it('will not open a review body while hidden', async () => {
    renderWithProviders(
      <AlbumReviewsTable reviews={reviews} loading={false} hidden onToggleHidden={() => {}} />,
    )
    await userEvent.click(screen.getByText('Mar 4, 2026'))
    expect(screen.queryByText('"A total knockout."')).not.toBeInTheDocument()
  })

  it('withdraws both blurred sorts while hidden, so the row order cannot rank them', () => {
    const { rerender } = renderWithProviders(
      <AlbumReviewsTable reviews={reviews} loading={false} hidden onToggleHidden={() => {}} />,
    )
    expect(screen.queryByRole('button', { name: /^rating/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^reviewer/i })).not.toBeInTheDocument()
    // Date is still rankable — it gives nothing away.
    expect(screen.getByRole('button', { name: /^date/i })).toBeInTheDocument()

    rerender(
      <AlbumReviewsTable reviews={reviews} loading={false} hidden={false} onToggleHidden={() => {}} />,
    )
    expect(screen.getByRole('button', { name: /^rating/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^reviewer/i })).toBeInTheDocument()
  })

  it('does not carry a rating sort chosen before the guard went back up', async () => {
    const { rerender } = renderWithProviders(
      <AlbumReviewsTable reviews={reviews} loading={false} hidden={false} onToggleHidden={() => {}} />,
    )
    await userEvent.click(screen.getByRole('button', { name: /^rating/i }))
    expect(screen.getAllByRole('row')[1]).toHaveTextContent('alex')  // ascending by rating

    rerender(
      <AlbumReviewsTable reviews={reviews} loading={false} hidden onToggleHidden={() => {}} />,
    )
    // Back on date, keeping the ascending direction — kate reviewed first.
    expect(screen.getAllByRole('row')[1]).toHaveTextContent('kate')
    expect(screen.getAllByRole('row')[2]).toHaveTextContent('alex')
  })

  it('still flips the date order on the first click after the guard goes back up', async () => {
    const { rerender } = renderWithProviders(
      <AlbumReviewsTable reviews={reviews} loading={false} hidden={false} onToggleHidden={() => {}} />,
    )
    await userEvent.click(screen.getByRole('button', { name: /^reviewer/i }))

    rerender(
      <AlbumReviewsTable reviews={reviews} loading={false} hidden onToggleHidden={() => {}} />,
    )
    // Reviewer sort was withdrawn, so Date is in effect and already ascending.
    expect(screen.getAllByRole('row')[1]).toHaveTextContent('kate')

    // Clicking the header it is showing has to reverse it, not re-set ascending.
    await userEvent.click(screen.getByRole('button', { name: /^date/i }))
    expect(screen.getAllByRole('row')[1]).toHaveTextContent('alex')
  })

  it('sorts by reviewer on demand', async () => {
    renderWithProviders(<AlbumReviewsTable reviews={reviews} loading={false} hidden={false} />)
    await userEvent.click(screen.getByRole('button', { name: /^reviewer/i }))
    expect(screen.getAllByRole('row')[1]).toHaveTextContent('alex')
    await userEvent.click(screen.getByRole('button', { name: /^reviewer/i }))
    expect(screen.getAllByRole('row')[1]).toHaveTextContent('kate')
  })

  it('offers the toggle only to a viewer with something to reveal', () => {
    const onToggleHidden = vi.fn()
    const { rerender } = renderWithProviders(
      <AlbumReviewsTable reviews={reviews} loading={false} hidden={false} />,
    )
    expect(screen.queryByRole('button', { name: /reviews$/i })).not.toBeInTheDocument()

    rerender(
      <AlbumReviewsTable reviews={reviews} loading={false} hidden onToggleHidden={onToggleHidden} />,
    )
    expect(screen.getByRole('button', { name: /show reviews/i })).toBeInTheDocument()
  })

  it('says so when nobody has reviewed the album', () => {
    renderWithProviders(<AlbumReviewsTable reviews={[]} loading={false} hidden={false} />)
    expect(screen.getByText('No reviews yet.')).toBeInTheDocument()
    expect(screen.getByText('0 reviews')).toBeInTheDocument()
  })

  it('notes a review left without any text', async () => {
    renderWithProviders(
      <AlbumReviewsTable reviews={[review({ comment: null })]} loading={false} hidden={false} />,
    )
    await userEvent.click(screen.getByText('kate'))
    expect(screen.getByText('No notes left.')).toBeInTheDocument()
  })
})
