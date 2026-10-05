import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/renderWithProviders'
import AlbumRatingSummary from './AlbumRatingSummary'
import type { AlbumStatsResponse } from '../../types/album'

/** The SpoilerBlur wrapper around a node, present only while it is hidden. */
function blurWrapper(el: HTMLElement): HTMLElement | null {
  return el.closest('[aria-hidden="true"]')
}

const stats: AlbumStatsResponse = {
  average_rating: 8.42,
  rating_stddev: 1.3,
  review_count: 4,
  nomination_count: 2,
  histogram: [
    { bucket_start: 7, bucket_end: 8, count: 1 },
    { bucket_start: 8, bucket_end: 9, count: 3 },
  ],
}

describe('AlbumRatingSummary', () => {
  it('shows the score outright when nothing is hidden', () => {
    renderWithProviders(<AlbumRatingSummary stats={stats} loading={false} hidden={false} />)
    expect(blurWrapper(screen.getByText('8.4'))).toBeNull()
    expect(screen.getByText('± 1.3 (1σ)')).toBeInTheDocument()
  })

  it('strips the band color off the score while hidden, since color survives a blur', () => {
    const { rerender } = renderWithProviders(
      <AlbumRatingSummary stats={stats} loading={false} hidden onToggleHidden={() => {}} />,
    )
    // 8.4 sits in the blue band — a blue smear would read as an 8 on its own.
    expect(screen.getByText('8.4').getAttribute('style')).toContain('--mantine-color-gray-5')
    expect(screen.getByText('8.4').getAttribute('style')).not.toContain('blue')

    rerender(<AlbumRatingSummary stats={stats} loading={false} hidden={false} />)
    expect(screen.getByText('8.4').getAttribute('style')).toContain('--mantine-color-blue-6')
  })

  it('blurs the score and the spread while hidden', () => {
    renderWithProviders(
      <AlbumRatingSummary stats={stats} loading={false} hidden onToggleHidden={() => {}} />,
    )
    expect(blurWrapper(screen.getByText('8.4'))?.getAttribute('style')).toContain('blur(14px)')
    expect(blurWrapper(screen.getByText('± 1.3 (1σ)'))?.getAttribute('style')).toContain('blur(')
    expect(screen.getByText('Global rating hidden')).toBeInTheDocument()
  })

  it('takes the histogram out of the page rather than blurring it', () => {
    const { container, rerender } = renderWithProviders(
      <AlbumRatingSummary stats={stats} loading={false} hidden onToggleHidden={() => {}} />,
    )
    // A blurred chart still shows where the bars stand and how tall they are,
    // so nothing of it is rendered at all.
    expect(container.querySelector('.recharts-responsive-container')).toBeNull()
    expect(screen.getByText('Rating distribution hidden')).toBeInTheDocument()

    rerender(<AlbumRatingSummary stats={stats} loading={false} hidden={false} />)
    expect(container.querySelector('.recharts-responsive-container')).not.toBeNull()
    expect(screen.queryByText('Rating distribution hidden')).not.toBeInTheDocument()
  })

  it('stands the placeholder at the chart height, so revealing does not reflow the card', () => {
    const { container, rerender } = renderWithProviders(
      <AlbumRatingSummary stats={stats} loading={false} hidden onToggleHidden={() => {}} />,
    )
    const placeholder = screen.getByText('Rating distribution hidden').closest('div')?.parentElement
    expect(placeholder?.getAttribute('style')).toContain('height: 100px')

    rerender(<AlbumRatingSummary stats={stats} loading={false} hidden={false} />)
    const chart = container.querySelector('.recharts-responsive-container') as HTMLElement
    expect(chart.getAttribute('style')).toContain('height: 100px')
  })

  it('leaves the review count readable while hidden, so the page still says how many', () => {
    renderWithProviders(
      <AlbumRatingSummary stats={stats} loading={false} hidden onToggleHidden={() => {}} />,
    )
    expect(blurWrapper(screen.getByText('4 reviews'))).toBeNull()
  })

  it('explains why the score is missing and offers to reveal it', async () => {
    const onToggleHidden = vi.fn()
    renderWithProviders(
      <AlbumRatingSummary stats={stats} loading={false} hidden onToggleHidden={onToggleHidden} />,
    )
    expect(screen.getByText(/hidden until you post your review/i)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /show global score/i }))
    expect(onToggleHidden).toHaveBeenCalledTimes(1)
  })

  it('renders no toggle for a viewer with nothing to reveal', () => {
    renderWithProviders(<AlbumRatingSummary stats={stats} loading={false} hidden={false} />)
    expect(screen.queryByRole('button', { name: /global score/i })).not.toBeInTheDocument()
  })

  it('falls back to a dash when no one has rated the album', () => {
    renderWithProviders(
      <AlbumRatingSummary
        stats={{ average_rating: null, rating_stddev: null, review_count: 0, nomination_count: 0, histogram: [] }}
        loading={false}
        hidden={false}
      />,
    )
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.getByText('0 reviews')).toBeInTheDocument()
  })

  it('shows a skeleton instead of the stats while they load', () => {
    renderWithProviders(<AlbumRatingSummary stats={undefined} loading hidden={false} />)
    expect(screen.queryByText('Global Rating')).not.toBeInTheDocument()
  })
})
