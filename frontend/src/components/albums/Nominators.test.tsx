import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/renderWithProviders'
import { NominatorLinks, NominatorSummary } from './Nominators'

describe('NominatorSummary', () => {
  it('shows a dash when there are no nominators', () => {
    renderWithProviders(<NominatorSummary usernames={[]} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('shows the lone nominator by name', () => {
    renderWithProviders(<NominatorSummary usernames={['kate']} />)
    expect(screen.getByText('kate')).toBeInTheDocument()
    expect(screen.queryByText(/Multiple/)).not.toBeInTheDocument()
  })

  it('collapses several nominators and lists them on hover', async () => {
    renderWithProviders(<NominatorSummary usernames={['alex', 'kate', 'sam']} />)
    const summary = screen.getByRole('button', { name: 'Nominated by alex, kate, sam' })
    expect(summary).toHaveTextContent('Multiple (3)')

    await userEvent.hover(summary)
    expect(await screen.findByText('sam')).toBeInTheDocument()
  })

  it('does not let a tap bubble up to the row it sits in', async () => {
    const onRowClick = vi.fn()
    renderWithProviders(
      <div onClick={onRowClick}>
        <NominatorSummary usernames={['alex', 'kate']} />
      </div>,
    )
    await userEvent.click(screen.getByText('Multiple (2)'))
    expect(onRowClick).not.toHaveBeenCalled()
  })
})

describe('NominatorLinks', () => {
  it('links each nominator to their profile', () => {
    renderWithProviders(<NominatorLinks usernames={['alex', 'kate', 'sam']} />)
    expect(screen.getByRole('link', { name: 'kate' })).toHaveAttribute('href', '/users/kate')
    expect(screen.getAllByRole('link')).toHaveLength(3)
  })

  it('renders nothing for an empty list', () => {
    renderWithProviders(<NominatorLinks usernames={[]} />)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.queryByText(/and/)).not.toBeInTheDocument()
  })
})
