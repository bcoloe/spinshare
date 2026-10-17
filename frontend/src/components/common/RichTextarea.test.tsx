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
})
