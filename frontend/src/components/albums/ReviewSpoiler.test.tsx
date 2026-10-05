import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ratingColorHex } from '../../utils/ratingColor'
import { themeColorHex } from '../../utils/themeColorHex'
import { SPOILER_COLOR, SpoilerBlur, SpoilerToggle } from './ReviewSpoiler'

describe('SPOILER_COLOR', () => {
  it('sits on no rating band, so it gives nothing away', () => {
    const neutral = themeColorHex(SPOILER_COLOR)
    expect(neutral).toMatch(/^#[0-9a-f]{6}$/i)

    // Every band the scale can paint, including the perfect-10 top band.
    const bandColors = Array.from({ length: 12 }, (_, i) => ratingColorHex(i * (10 / 11)))
    expect(bandColors).not.toContain(neutral)
    expect(ratingColorHex(10)).not.toBe(neutral)
  })
})

describe('SpoilerBlur', () => {
  it('leaves the content alone when nothing is hidden', () => {
    renderWithProviders(<SpoilerBlur hidden={false}>8.4</SpoilerBlur>)
    const wrapper = screen.getByText('8.4')
    expect(wrapper).not.toHaveAttribute('aria-hidden')
    expect(wrapper.getAttribute('style') ?? '').not.toContain('blur')
  })

  it('blurs the content and makes it inert while hidden', () => {
    renderWithProviders(<SpoilerBlur hidden strength={9}>8.4</SpoilerBlur>)
    const wrapper = screen.getByText('8.4')
    expect(wrapper).toHaveAttribute('aria-hidden', 'true')
    expect(wrapper.getAttribute('style')).toContain('blur(9px)')
    expect(wrapper.getAttribute('style')).toContain('pointer-events: none')
    expect(wrapper.getAttribute('style')).toContain('user-select: none')
  })

  it('keeps layout styles in both states', () => {
    const { rerender } = renderWithProviders(
      <SpoilerBlur hidden style={{ flex: 1 }}>8.4</SpoilerBlur>,
    )
    expect(screen.getByText('8.4').getAttribute('style')).toContain('flex: 1')

    rerender(<SpoilerBlur hidden={false} style={{ flex: 1 }}>8.4</SpoilerBlur>)
    expect(screen.getByText('8.4').getAttribute('style')).toContain('flex: 1')
  })

  it('substitutes the label for screen readers only while hidden', () => {
    const { rerender } = renderWithProviders(
      <SpoilerBlur hidden label="Rating hidden">8.4</SpoilerBlur>,
    )
    expect(screen.getByText('Rating hidden')).toBeInTheDocument()

    rerender(<SpoilerBlur hidden={false} label="Rating hidden">8.4</SpoilerBlur>)
    expect(screen.queryByText('Rating hidden')).not.toBeInTheDocument()
  })
})

describe('SpoilerToggle', () => {
  it('offers to reveal while hidden and to re-hide once shown', async () => {
    const onToggle = vi.fn()
    const { rerender } = renderWithProviders(
      <SpoilerToggle hidden onToggle={onToggle} subject="reviews" />,
    )

    await userEvent.click(screen.getByRole('button', { name: /show reviews/i }))
    expect(onToggle).toHaveBeenCalledTimes(1)

    rerender(<SpoilerToggle hidden={false} onToggle={onToggle} subject="reviews" />)
    expect(screen.getByRole('button', { name: /hide reviews/i })).toBeInTheDocument()
  })

  it('names its own subject, so two guards on one page stay distinguishable', () => {
    renderWithProviders(<SpoilerToggle hidden onToggle={() => {}} subject="global score" />)
    expect(screen.getByRole('button', { name: 'Show global score' })).toBeInTheDocument()
  })

  it('explains on hover why that subject is not showing', async () => {
    renderWithProviders(<SpoilerToggle hidden onToggle={() => {}} subject="global score" />)

    await userEvent.hover(screen.getByRole('button', { name: /show global score/i }))
    expect(
      await screen.findByText(/haven't reviewed this album yet — seeing the global score first/i),
    ).toBeInTheDocument()
  })

  it('explains on hover what re-hiding does', async () => {
    renderWithProviders(<SpoilerToggle hidden={false} onToggle={() => {}} subject="reviews" />)

    await userEvent.hover(screen.getByRole('button', { name: /hide reviews/i }))
    expect(await screen.findByText('Put the reviews back behind the blur.')).toBeInTheDocument()
  })
})
