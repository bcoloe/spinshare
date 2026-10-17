import { useState } from 'react'
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import RichTextarea from './RichTextarea'
import type { GroupMemberResponse } from '../../types/group'

function Harness({ members }: { members?: GroupMemberResponse[] }) {
  const [value, setValue] = useState('')
  return <RichTextarea value={value} onChange={setValue} members={members} maxLength={100} />
}

function setup(members?: GroupMemberResponse[]) {
  const user = userEvent.setup()
  render(
    <MantineProvider>
      <Harness members={members} />
    </MantineProvider>,
  )
  const textarea = screen.getByRole('textbox') as HTMLTextAreaElement
  return { user, textarea }
}

describe('RichTextarea', () => {
  it('bolds the selection from the toolbar', async () => {
    const { user, textarea } = setup()
    await user.type(textarea, 'so good')
    textarea.setSelectionRange(3, 7)
    await user.pointer({ keys: '[MouseLeft>]', target: screen.getByRole('button', { name: 'Bold' }) })

    expect(textarea.value).toBe('so **good**')
  })

  it('italicises the selection with Ctrl+I', async () => {
    const { user, textarea } = setup()
    await user.type(textarea, 'so good')
    textarea.setSelectionRange(3, 7)
    await user.keyboard('{Control>}i{/Control}')

    expect(textarea.value).toBe('so *good*')
  })

  it('offers no mention suggestions without members', async () => {
    const { user, textarea } = setup()
    await user.type(textarea, 'hey @al')

    expect(screen.queryByText('@alice')).not.toBeInTheDocument()
  })

  it('offers emoji suggestions for a shortcode', async () => {
    const { user, textarea } = setup()
    await user.type(textarea, 'hot :fir')

    expect(screen.getByText(':fire:')).toBeInTheDocument()
  })

  it('keeps the suggestion list closed after Escape', async () => {
    const { user, textarea } = setup()
    await user.type(textarea, 'hot :fir')
    expect(screen.getByText(':fire:')).toBeInTheDocument()

    // user.keyboard sends keydown *and* keyup; the keyup must not reopen it.
    await user.keyboard('{Escape}')
    expect(screen.queryByText(':fire:')).not.toBeInTheDocument()

    await user.type(textarea, 'e')
    expect(screen.getByText(':fire:')).toBeInTheDocument()
  })

  it('turns a typed-out shortcode into its emoji', async () => {
    const { user, textarea } = setup()
    await user.type(textarea, 'so :fire: ')
    expect(textarea.value).toBe('so 🔥 ')
  })

  it('leaves colon-separated numbers alone', async () => {
    const { user, textarea } = setup()
    await user.type(textarea, 'at 12:30:45')
    expect(textarea.value).toBe('at 12:30:45')
  })

  it('does not substitute text after the caret when typing before it', async () => {
    const { user, textarea } = setup()
    await user.type(textarea, 'ratio 1:100:5')
    textarea.setSelectionRange(7, 7) // just after the "1"
    await user.type(textarea, '1', { initialSelectionStart: 7, initialSelectionEnd: 7 })
    expect(textarea.value).toBe('ratio 11:100:5')
  })
})
