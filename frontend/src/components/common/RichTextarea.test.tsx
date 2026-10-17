import { useState } from 'react'
import { describe, it, expect, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import RichTextarea from './RichTextarea'
import type { GroupMemberResponse } from '../../types/group'
import { getEditor, pressKey, selectText, storedText, typeText } from '../../test/editor'

const MEMBERS = [
  { user_id: 1, username: 'alice', role: 'owner', joined_at: '', first_name: null, last_name: null, name_is_public: false },
] as GroupMemberResponse[]

let setOutside: (v: string) => void = () => {}
let latestValue = ''

function Harness({ members, maxLength = 100, initial = '' }: { members?: GroupMemberResponse[]; maxLength?: number; initial?: string }) {
  const [value, setValue] = useState(initial)
  setOutside = setValue
  latestValue = value
  return <RichTextarea value={value} onChange={setValue} members={members} maxLength={maxLength} label="Comment" />
}

function setup(props: Parameters<typeof Harness>[0] = {}) {
  render(
    <MantineProvider>
      <Harness {...props} />
    </MantineProvider>,
  )
  return getEditor()
}

describe('RichTextarea', () => {
  describe('formatting as you type', () => {
    it('turns **word** bold and stores the markers', () => {
      const editor = setup()
      typeText(editor, 'so **good** ')

      expect(editor.view.dom.querySelector('strong')?.textContent).toBe('good')
      expect(editor.view.dom.textContent).not.toContain('*')
      expect(latestValue).toBe('so **good** ')
    })

    it('turns *word* italic', () => {
      const editor = setup()
      typeText(editor, 'so *good* ')

      expect(editor.view.dom.querySelector('em')?.textContent).toBe('good')
      expect(latestValue).toBe('so *good* ')
    })

    it('turns _word_ italic', () => {
      const editor = setup()
      typeText(editor, 'so _good_ ')

      expect(editor.view.dom.querySelector('em')?.textContent).toBe('good')
      expect(latestValue).toBe('so *good* ')
    })

    it('leaves underscores inside words alone', () => {
      const editor = setup()
      typeText(editor, 'snake_case_name ')

      expect(editor.view.dom.querySelector('em')).toBeNull()
      expect(latestValue).toBe('snake_case_name ')
    })

    it('stores an asterisk typed as text so it stays literal', () => {
      const editor = setup()
      typeText(editor, '2 * 3')

      expect(latestValue).toBe('2 \\* 3')
    })

    it('shows stored formatting as formatting', () => {
      const editor = setup({ initial: 'a **loud** word' })

      expect(editor.view.dom.querySelector('strong')?.textContent).toBe('loud')
      expect(editor.view.dom.textContent).toBe('a loud word')
    })
  })

  describe('shortcuts and toolbar', () => {
    it('bolds the selection with Ctrl+B', () => {
      const editor = setup({ initial: 'so good' })
      selectText(editor, 'good')
      pressKey(editor, 'b', { ctrlKey: true })

      expect(latestValue).toBe('so **good**')
    })

    it('italicises the selection from the toolbar', async () => {
      const editor = setup({ initial: 'so good' })
      selectText(editor, 'good')
      await userEvent.click(screen.getByRole('button', { name: 'Italic' }))

      expect(storedText(editor)).toBe('so *good*')
    })

    it('inserts an emoji from the picker', async () => {
      const editor = setup()
      typeText(editor, 'hot ')
      await userEvent.click(screen.getByRole('button', { name: 'Insert emoji' }))
      await userEvent.click(await screen.findByLabelText('fire'))

      expect(storedText(editor)).toBe('hot 🔥')
    })
  })

  describe('emoji', () => {
    it('turns a typed-out shortcode into its emoji', () => {
      const editor = setup()
      typeText(editor, 'so :fire:')

      expect(latestValue).toBe('so 🔥')
    })

    it('leaves a code that starts mid-word alone', () => {
      const editor = setup()
      typeText(editor, 'ratio 1:100:5')

      expect(latestValue).toBe('ratio 1:100:5')
    })

    it('offers and completes a partial shortcode', async () => {
      const editor = setup()
      typeText(editor, 'hot :fir')
      expect(await screen.findByText(':fire:')).toBeInTheDocument()

      pressKey(editor, 'Enter')
      expect(latestValue).toBe('hot 🔥 ')
    })

    it('keeps the list closed after Escape until the query changes', async () => {
      const editor = setup()
      typeText(editor, 'hot :fir')
      await screen.findByText(':fire:')
      pressKey(editor, 'Escape')
      expect(screen.queryByText(':fire:')).not.toBeInTheDocument()

      typeText(editor, 'e')
      expect(await screen.findByText(':fire:')).toBeInTheDocument()
    })

    it('does not open the list for a lone colon', () => {
      const editor = setup()
      typeText(editor, 'meet at 12:')
      expect(screen.queryByText(/^:.+:$/)).not.toBeInTheDocument()
    })
  })

  describe('mentions', () => {
    it('offers none without members', () => {
      const editor = setup()
      typeText(editor, 'hey @al')
      expect(screen.queryByText('@alice')).not.toBeInTheDocument()
    })

    it('offers and completes members', async () => {
      const editor = setup({ members: MEMBERS })
      typeText(editor, 'hey @al')
      expect(await screen.findByText('@alice')).toBeInTheDocument()

      pressKey(editor, 'Enter')
      expect(latestValue).toBe('hey @alice ')
    })
  })

  it('takes outside changes to the value', () => {
    const editor = setup({ initial: 'draft' })
    act(() => setOutside('**restored**'))

    expect(editor.view.dom.querySelector('strong')?.textContent).toBe('restored')
  })

  it('refuses input past the stored-length limit', () => {
    const editor = setup({ maxLength: 5 })
    typeText(editor, 'abcdefg')

    expect(latestValue).toBe('abcde')
  })

  it('is labelled by its label', () => {
    setup()
    expect(screen.getByRole('textbox', { name: 'Comment' })).toBeInTheDocument()
  })

  it('reports no change until the user edits', () => {
    // Draft autosave treats any onChange as typing; a spurious one on mount
    // once saved an empty draft over a real one.
    const onChange = vi.fn()
    const { rerender } = render(
      <MantineProvider>
        <RichTextarea value="**kept**" onChange={onChange} maxLength={100} />
      </MantineProvider>,
    )
    rerender(
      <MantineProvider>
        <RichTextarea value="**kept**" onChange={onChange} maxLength={100} disabled />
      </MantineProvider>,
    )
    rerender(
      <MantineProvider>
        <RichTextarea value="**kept**" onChange={onChange} maxLength={100} />
      </MantineProvider>,
    )

    expect(onChange).not.toHaveBeenCalled()
  })
})
