import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import MessageComposer from './MessageComposer'
import type { GroupMemberResponse } from '../../types/group'
import { getEditor, pressKey, storedText, typeText } from '../../test/editor'

function member(user_id: number, username: string, role: 'owner' | 'member'): GroupMemberResponse {
  return {
    user_id,
    username,
    role,
    joined_at: '2026-01-01T00:00:00Z',
    first_name: null,
    last_name: null,
    name_is_public: false,
  }
}

const MEMBERS: GroupMemberResponse[] = [member(1, 'alice', 'owner'), member(2, 'bob', 'member')]

function renderComposer(props: Partial<Parameters<typeof MessageComposer>[0]> = {}) {
  const onSend = vi.fn()
  render(
    <MantineProvider>
      <MessageComposer members={MEMBERS} onSend={onSend} isSending={false} {...props} />
    </MantineProvider>,
  )
  return { onSend, editor: getEditor() }
}

describe('MessageComposer', () => {
  it('sends on Enter and clears', () => {
    const { editor, onSend } = renderComposer()
    typeText(editor, 'great record')
    pressKey(editor, 'Enter')

    expect(onSend).toHaveBeenCalledWith('great record')
    expect(storedText(editor)).toBe('')
  })

  it('inserts a line break on Shift+Enter instead of sending', () => {
    const { editor, onSend } = renderComposer()
    typeText(editor, 'one')
    pressKey(editor, 'Enter', { shiftKey: true })
    typeText(editor, 'two')

    expect(onSend).not.toHaveBeenCalled()
    expect(storedText(editor)).toBe('one\ntwo')
  })

  it('sends formatting as stored markers', () => {
    const { editor, onSend } = renderComposer()
    typeText(editor, 'this is **huge** ')
    pressKey(editor, 'Enter')

    expect(onSend).toHaveBeenCalledWith('this is **huge**')
  })

  it('does not send an empty message', () => {
    const { editor, onSend } = renderComposer()
    typeText(editor, '   ')
    pressKey(editor, 'Enter')

    expect(onSend).not.toHaveBeenCalled()
  })

  it('sends from the send button', async () => {
    const { editor, onSend } = renderComposer()
    typeText(editor, 'hi')
    await userEvent.click(screen.getByRole('button', { name: 'Send message' }))

    expect(onSend).toHaveBeenCalledWith('hi')
  })

  it('sends a picked emoji as a plain character', async () => {
    const { editor, onSend } = renderComposer()
    typeText(editor, 'yes ')
    await userEvent.click(screen.getByRole('button', { name: 'Insert emoji' }))
    await userEvent.click(await screen.findByLabelText('fire'))
    pressKey(editor, 'Enter')

    expect(onSend).toHaveBeenCalledWith('yes 🔥')
  })

  it('converts a typed-out shortcode', () => {
    const { editor, onSend } = renderComposer()
    typeText(editor, 'closing track is :fire:')
    pressKey(editor, 'Enter')

    expect(onSend).toHaveBeenCalledWith('closing track is 🔥')
  })

  it('leaves an unknown shortcode alone', () => {
    const { editor, onSend } = renderComposer()
    typeText(editor, 'ship :not_an_emoji:')
    pressKey(editor, 'Enter')

    expect(onSend).toHaveBeenCalledWith('ship :not_an_emoji:')
  })

  it('completes a mention on Enter without sending', async () => {
    const { editor, onSend } = renderComposer()
    typeText(editor, 'hey @al')
    await screen.findByText('@alice')
    pressKey(editor, 'Enter')

    expect(storedText(editor)).toBe('hey @alice ')
    expect(onSend).not.toHaveBeenCalled()
  })

  it('completes a shortcode to its character on Enter without sending', async () => {
    const { editor, onSend } = renderComposer()
    typeText(editor, 'so :gui')
    await screen.findByText(':guitar:')
    pressKey(editor, 'Enter')

    expect(storedText(editor)).toBe('so 🎸 ')
    expect(onSend).not.toHaveBeenCalled()
  })

  it('disables entry when the user cannot post', () => {
    const { editor } = renderComposer({ disabled: true })

    expect(editor.view.dom).toHaveAttribute('contenteditable', 'false')
    expect(screen.getByRole('button', { name: 'Insert emoji' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Bold' })).toBeDisabled()
  })
})
