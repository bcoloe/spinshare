import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MantineProvider } from '@mantine/core'
import MessageComposer from './MessageComposer'
import type { GroupMemberResponse } from '../../types/group'

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
  const utils = render(
    <MantineProvider>
      <MessageComposer members={MEMBERS} onSend={onSend} isSending={false} {...props} />
    </MantineProvider>,
  )
  const textarea = screen.getByRole('textbox') as HTMLTextAreaElement
  return { ...utils, onSend, textarea }
}

async function pickEmoji(user: ReturnType<typeof userEvent.setup>, slug: string) {
  await user.click(screen.getByRole('button', { name: 'Insert emoji' }))
  await waitFor(() => expect(screen.getByLabelText('Search emoji')).toBeInTheDocument())
  await user.click(screen.getByLabelText(slug))
}

describe('MessageComposer', () => {
  describe('emoji picker insertion', () => {
    it('appends the emoji when the caret is at the end', async () => {
      const user = userEvent.setup()
      const { textarea } = renderComposer()

      await user.type(textarea, 'this rules ')
      await pickEmoji(user, 'fire')

      expect(textarea.value).toBe('this rules 🔥')
    })

    it('inserts at the caret rather than the end', async () => {
      const user = userEvent.setup()
      const { textarea } = renderComposer()

      await user.type(textarea, 'ab')
      await user.keyboard('{ArrowLeft}')
      await pickEmoji(user, 'fire')

      expect(textarea.value).toBe('a🔥b')
    })

    it('leaves the caret after the inserted emoji so typing continues', async () => {
      const user = userEvent.setup()
      const { textarea } = renderComposer()

      await user.type(textarea, 'wow ')
      await pickEmoji(user, 'fire')
      await user.type(textarea, '!')

      expect(textarea.value).toBe('wow 🔥!')
    })

    it('sends the picked emoji as a plain character', async () => {
      const user = userEvent.setup()
      const { textarea, onSend } = renderComposer()

      await user.type(textarea, 'yes ')
      await pickEmoji(user, 'fire')
      await user.type(textarea, '{Enter}')

      expect(onSend).toHaveBeenCalledWith('yes 🔥')
    })
  })

  describe('shortcode substitution', () => {
    it('converts a typed-out shortcode on send', async () => {
      const user = userEvent.setup()
      const { textarea, onSend } = renderComposer()

      await user.type(textarea, 'closing track is :fire:{Enter}')

      expect(onSend).toHaveBeenCalledWith('closing track is 🔥')
    })

    it('leaves an unknown shortcode alone', async () => {
      const user = userEvent.setup()
      const { textarea, onSend } = renderComposer()

      await user.type(textarea, 'ship :not_an_emoji:{Enter}')

      expect(onSend).toHaveBeenCalledWith('ship :not_an_emoji:')
    })
  })

  describe('autocomplete', () => {
    it('offers members for a partial @handle', async () => {
      const user = userEvent.setup()
      const { textarea } = renderComposer()

      await user.type(textarea, 'hey @al')

      expect(screen.getByText('@alice')).toBeInTheDocument()
    })

    it('completes a mention on Enter without sending', async () => {
      const user = userEvent.setup()
      const { textarea, onSend } = renderComposer()

      await user.type(textarea, 'hey @al{Enter}')

      expect(textarea.value).toBe('hey @alice ')
      expect(onSend).not.toHaveBeenCalled()
    })

    it('offers emoji for a partial shortcode', async () => {
      const user = userEvent.setup()
      const { textarea } = renderComposer()

      await user.type(textarea, 'so :gui')

      expect(screen.getByText(':guitar:')).toBeInTheDocument()
    })

    it('completes a shortcode to its character on Enter', async () => {
      const user = userEvent.setup()
      const { textarea, onSend } = renderComposer()

      await user.type(textarea, 'so :gui{Enter}')

      expect(textarea.value).toBe('so 🎸 ')
      expect(onSend).not.toHaveBeenCalled()
    })

    it('does not open the picker for a lone colon', async () => {
      const user = userEvent.setup()
      const { textarea } = renderComposer()

      await user.type(textarea, 'meet at 12:')

      expect(screen.queryByText(/^:.+:$/)).not.toBeInTheDocument()
    })
  })

  it('disables entry when the user cannot post', () => {
    const { textarea } = renderComposer({ disabled: true })

    expect(textarea).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Insert emoji' })).toBeDisabled()
  })
})
