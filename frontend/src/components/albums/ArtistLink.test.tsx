import { describe, expect, it, vi } from 'vitest'
import { fireEvent, screen } from '@testing-library/react'
import { renderWithProviders } from '../../test/renderWithProviders'
import ArtistLink from './ArtistLink'

describe('ArtistLink', () => {
  it('links to the encoded artist page', () => {
    renderWithProviders(<ArtistLink artist="AC/DC & Friends" />)
    expect(screen.getByRole('link', { name: 'AC/DC & Friends' })).toHaveAttribute(
      'href',
      '/artists/AC%2FDC%20%26%20Friends',
    )
  })

  it('does not trigger a clickable parent', () => {
    const onParentClick = vi.fn()
    renderWithProviders(
      <div onClick={onParentClick}>
        <ArtistLink artist="Radiohead" />
      </div>,
    )
    fireEvent.click(screen.getByRole('link', { name: 'Radiohead' }))
    expect(onParentClick).not.toHaveBeenCalled()
  })
})
