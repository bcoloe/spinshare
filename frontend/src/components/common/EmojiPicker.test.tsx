import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import EmojiPicker from './EmojiPicker'

function renderPicker(props: Partial<Parameters<typeof EmojiPicker>[0]> = {}) {
  const onSelect = vi.fn()
  const utils = render(
    <MantineProvider>
      <EmojiPicker onSelect={onSelect} {...props} />
    </MantineProvider>,
  )
  return { ...utils, onSelect }
}

async function open(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'Insert emoji' }))
  await waitFor(() => expect(screen.getByLabelText('Search emoji')).toBeInTheDocument())
}

describe('EmojiPicker', () => {
  it('is closed until the button is clicked', () => {
    renderPicker()
    expect(screen.queryByLabelText('Search emoji')).not.toBeInTheDocument()
  })

  it('opens a browsable grid grouped by category', async () => {
    const user = userEvent.setup()
    renderPicker()
    await open(user)

    expect(screen.getByText('Smileys')).toBeInTheDocument()
    expect(screen.getByText('Music')).toBeInTheDocument()
    expect(screen.getByLabelText('fire')).toBeInTheDocument()
  })

  it('reports the chosen emoji as a plain character', async () => {
    const user = userEvent.setup()
    const { onSelect } = renderPicker()
    await open(user)

    await user.click(screen.getByLabelText('fire'))

    expect(onSelect).toHaveBeenCalledWith('🔥')
  })

  it('closes after a selection', async () => {
    const user = userEvent.setup()
    renderPicker()
    await open(user)

    await user.click(screen.getByLabelText('fire'))

    await waitFor(() =>
      expect(screen.queryByLabelText('Search emoji')).not.toBeInTheDocument(),
    )
  })

  it('filters to matches when searching', async () => {
    const user = userEvent.setup()
    renderPicker()
    await open(user)

    await user.type(screen.getByLabelText('Search emoji'), 'guitar')

    expect(screen.getByLabelText('guitar')).toBeInTheDocument()
    // The browse headings give way to a flat result grid.
    expect(screen.queryByText('Smileys')).not.toBeInTheDocument()
  })

  it('finds an emoji by an alias rather than its slug', async () => {
    const user = userEvent.setup()
    renderPicker()
    await open(user)

    await user.type(screen.getByLabelText('Search emoji'), 'vinyl')

    expect(screen.getByLabelText('dvd')).toBeInTheDocument()
  })

  it('says so when nothing matches', async () => {
    const user = userEvent.setup()
    renderPicker()
    await open(user)

    await user.type(screen.getByLabelText('Search emoji'), 'zzzzzz')

    expect(screen.getByText(/No emoji matching/)).toBeInTheDocument()
  })

  it('cannot be opened while the composer is disabled', async () => {
    const user = userEvent.setup()
    renderPicker({ disabled: true })

    await user.click(screen.getByRole('button', { name: 'Insert emoji' }))

    expect(screen.queryByLabelText('Search emoji')).not.toBeInTheDocument()
  })
})
