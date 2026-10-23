import { describe, it, expect, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { getEditor, pressKey, selectText, typeText } from '../../test/editor'
import { MantineProvider } from '@mantine/core'
import { MemoryRouter } from 'react-router-dom'
import MessageList from './MessageList'
import type { MessageResponse } from '../../types/message'

function makeMessage(overrides: Partial<MessageResponse> = {}): MessageResponse {
  return {
    id: 1,
    group_id: 1,
    user_id: 1,
    username: 'alice',
    body: 'hello',
    created_at: '2026-08-16T12:00:00Z',
    edited_at: null,
    is_deleted: false,
    mentions: [],
    reactions: [],
    reactions_version: 0,
    ...overrides,
  }
}

function renderList(messages: MessageResponse[], props: Partial<Parameters<typeof MessageList>[0]> = {}) {
  return render(
    <MantineProvider>
      <MemoryRouter>
        <MessageList
          messages={messages}
          currentUserId={1}
          currentUsername="alice"
          canModerate={false}
          onlineIds={new Set()}
          onDelete={vi.fn()}
          members={[]}
          editingId={null}
          isSavingEdit={false}
          onStartEdit={vi.fn()}
          onCancelEdit={vi.fn()}
          onSaveEdit={vi.fn()}
          onToggleReaction={vi.fn()}
          hasOlder={false}
          isLoadingOlder={false}
          onLoadOlder={vi.fn()}
          {...props}
        />
      </MemoryRouter>
    </MantineProvider>,
  )
}

describe('MessageList', () => {
  it('shows an empty state when there are no messages', () => {
    renderList([])
    expect(screen.getByText('No messages yet')).toBeInTheDocument()
  })

  describe('scrollback', () => {
    it('marks the top of the list when there is nothing older', () => {
      renderList([makeMessage()], { hasOlder: false })
      expect(screen.getByText('Beginning of the conversation')).toBeInTheDocument()
    })

    it('does not claim the beginning while older pages may exist', () => {
      renderList([makeMessage()], { hasOlder: true })
      expect(screen.queryByText('Beginning of the conversation')).not.toBeInTheDocument()
    })

    it('shows a loader instead of the beginning marker while paging back', () => {
      renderList([makeMessage()], { hasOlder: true, isLoadingOlder: true })
      expect(screen.queryByText('Beginning of the conversation')).not.toBeInTheDocument()
      expect(document.querySelector('.mantine-Loader-root')).toBeInTheDocument()
    })

    it('requests an older page when the reader scrolls to the top', () => {
      const onLoadOlder = vi.fn()
      const { container } = renderList([makeMessage()], { hasOlder: true, onLoadOlder })

      const scroller = container.querySelector('[style*="overflow-y"]') as HTMLElement
      fireEvent.scroll(scroller, { target: { scrollTop: 0 } })

      expect(onLoadOlder).toHaveBeenCalledTimes(1)
    })

    it('does not request another page while one is already in flight', () => {
      const onLoadOlder = vi.fn()
      const { container } = renderList([makeMessage()], {
        hasOlder: true,
        isLoadingOlder: true,
        onLoadOlder,
      })

      const scroller = container.querySelector('[style*="overflow-y"]') as HTMLElement
      fireEvent.scroll(scroller, { target: { scrollTop: 0 } })

      expect(onLoadOlder).not.toHaveBeenCalled()
    })

    it('does not request an older page once the start is known', () => {
      const onLoadOlder = vi.fn()
      const { container } = renderList([makeMessage()], { hasOlder: false, onLoadOlder })

      const scroller = container.querySelector('[style*="overflow-y"]') as HTMLElement
      fireEvent.scroll(scroller, { target: { scrollTop: 0 } })

      expect(onLoadOlder).not.toHaveBeenCalled()
    })
  })

  it('renders a message body and author', () => {
    renderList([makeMessage({ body: 'great record' })])
    expect(screen.getByText('great record')).toBeInTheDocument()
    expect(screen.getByText('alice')).toBeInTheDocument()
  })

  describe('mention rendering', () => {
    it('highlights a handle the server resolved', () => {
      renderList([
        makeMessage({
          body: '@bob thoughts?',
          mentions: [{ user_id: 2, username: 'bob' }],
        }),
      ])

      const mention = screen.getByText('@bob')
      expect(mention).toBeInTheDocument()
      // Rendered as its own styled span, not swallowed into the body text.
      expect(mention.tagName.toLowerCase()).toBe('span')
    })

    it('leaves an unresolved handle as plain text', () => {
      // The server did not authorise this mention (not a group member), so it
      // must not render as a real one — this is the spoofing boundary.
      renderList([makeMessage({ body: '@nobody hi there', mentions: [] })])

      expect(screen.getByText('@nobody hi there')).toBeInTheDocument()
      expect(screen.queryByText('@nobody')).not.toBeInTheDocument()
    })

    it('highlights only the handles present in the mentions list', () => {
      renderList([
        makeMessage({
          body: '@bob and @mallory',
          mentions: [{ user_id: 2, username: 'bob' }],
        }),
      ])

      expect(screen.getByText('@bob')).toBeInTheDocument()
      expect(screen.queryByText('@mallory')).not.toBeInTheDocument()
    })

    it('matches handles case-insensitively', () => {
      renderList([
        makeMessage({ body: '@BOB hi', mentions: [{ user_id: 2, username: 'bob' }] }),
      ])
      expect(screen.getByText('@BOB')).toBeInTheDocument()
    })
  })

  describe('tombstones', () => {
    it('hides a deleted message entirely', () => {
      const { container } = renderList([
        makeMessage({ id: 1, body: 'kept' }),
        makeMessage({ id: 2, is_deleted: true, body: '' }),
      ])
      expect(screen.getByText('kept')).toBeInTheDocument()
      expect(container.querySelectorAll('.chat-message')).toHaveLength(1)
      expect(screen.queryByText('[message deleted]')).not.toBeInTheDocument()
    })

    it('shows the empty state when every message is deleted', () => {
      renderList([makeMessage({ is_deleted: true, body: '' })])
      expect(screen.getByText('No messages yet')).toBeInTheDocument()
    })

    it('renders a departed author as [deleted user]', () => {
      renderList([makeMessage({ user_id: null, username: null, body: 'still here' })])

      expect(screen.getByText('[deleted user]')).toBeInTheDocument()
      // The message itself survives so the conversation keeps its shape.
      expect(screen.getByText('still here')).toBeInTheDocument()
    })
  })

  describe('delete affordance', () => {
    it('offers delete on your own message', () => {
      renderList([makeMessage({ user_id: 1 })])
      expect(screen.getByLabelText('Delete message')).toBeInTheDocument()
    })

    it('hides delete on someone else’s message for a plain member', () => {
      renderList([makeMessage({ user_id: 2, username: 'bob' })])
      expect(screen.queryByLabelText('Delete message')).not.toBeInTheDocument()
    })

    it('offers delete on someone else’s message for a moderator', () => {
      renderList([makeMessage({ user_id: 2, username: 'bob' })], { canModerate: true })
      expect(screen.getByLabelText('Delete message')).toBeInTheDocument()
    })
  })

  describe('editing', () => {
    it('offers edit only on your own messages', () => {
      renderList([
        makeMessage({ id: 1, user_id: 1 }),
        makeMessage({ id: 2, user_id: 2, username: 'bob' }),
      ], { canModerate: true })
      expect(screen.getAllByLabelText('Edit message')).toHaveLength(1)
    })

    it('starts editing from the pencil', async () => {
      const onStartEdit = vi.fn()
      renderList([makeMessage({ id: 4, user_id: 1 })], { onStartEdit })
      await userEvent.click(screen.getByLabelText('Edit message'))
      expect(onStartEdit).toHaveBeenCalledWith(4)
    })

    it('saves the edited body on Enter', async () => {
      const onSaveEdit = vi.fn()
      renderList([makeMessage({ id: 4, user_id: 1, body: 'teh' })], { editingId: 4, onSaveEdit })
      const editor = getEditor()
      // autoFocus puts the caret at the end, ready to keep typing.
      expect(editor.state.selection.from).toBe(editor.state.doc.content.size - 1)
      selectText(editor, 'teh')
      typeText(editor, 'the')
      pressKey(editor, 'Enter')
      expect(onSaveEdit).toHaveBeenCalledWith(4, 'the')
    })

    it('cancels on Escape without saving', async () => {
      const onSaveEdit = vi.fn()
      const onCancelEdit = vi.fn()
      renderList([makeMessage({ id: 4, user_id: 1 })], { editingId: 4, onSaveEdit, onCancelEdit })
      const editor = getEditor()
      typeText(editor, 'more')
      pressKey(editor, 'Escape')
      expect(onCancelEdit).toHaveBeenCalled()
      expect(onSaveEdit).not.toHaveBeenCalled()
    })

    it('marks an edited message', () => {
      renderList([makeMessage({ edited_at: '2026-08-16T12:05:00Z' })])
      expect(screen.getByText('(edited)')).toBeInTheDocument()
    })
  })

  describe('reactions', () => {
    const fire = { emoji: '🔥', count: 2, user_ids: [1, 2] }
    const members = [
      { user_id: 1, username: 'alice', role: 'owner' as const, joined_at: '', first_name: null, last_name: null, name_is_public: false },
      { user_id: 2, username: 'bob', role: 'member' as const, joined_at: '', first_name: null, last_name: null, name_is_public: false },
    ]

    it('renders a chip per emoji with its count', () => {
      renderList([makeMessage({ reactions: [fire] })])
      expect(screen.getByLabelText('🔥 2')).toBeInTheDocument()
    })

    it('marks a chip you reacted with as pressed', () => {
      renderList([makeMessage({ reactions: [fire, { emoji: '👍', count: 1, user_ids: [2] }] })])
      expect(screen.getByLabelText('🔥 2')).toHaveAttribute('aria-pressed', 'true')
      expect(screen.getByLabelText('👍 1')).toHaveAttribute('aria-pressed', 'false')
    })

    it('clicking your chip withdraws the reaction', async () => {
      const onToggleReaction = vi.fn()
      renderList([makeMessage({ id: 3, reactions: [fire] })], { onToggleReaction, members })
      await userEvent.click(screen.getByLabelText('🔥 2'))
      expect(onToggleReaction).toHaveBeenCalledWith(3, '🔥', true)
    })

    it('clicking someone else’s chip adds yours', async () => {
      const onToggleReaction = vi.fn()
      renderList(
        [makeMessage({ id: 3, reactions: [{ emoji: '👍', count: 1, user_ids: [2] }] })],
        { onToggleReaction },
      )
      await userEvent.click(screen.getByLabelText('👍 1'))
      expect(onToggleReaction).toHaveBeenCalledWith(3, '👍', false)
    })

    it('reacts from the quick picker', async () => {
      const onToggleReaction = vi.fn()
      renderList([makeMessage({ id: 3 })], { onToggleReaction })
      await userEvent.click(screen.getByLabelText('Add reaction'))
      await userEvent.click(await screen.findByLabelText('React 😂'))
      expect(onToggleReaction).toHaveBeenCalledWith(3, '😂', false)
    })

    it('does not withdraw when picking an emoji you already used', async () => {
      const onToggleReaction = vi.fn()
      renderList([makeMessage({ id: 3, reactions: [fire] })], { onToggleReaction })
      await userEvent.click(screen.getByLabelText('Add reaction'))
      await userEvent.click(await screen.findByLabelText('React 🔥'))
      expect(onToggleReaction).not.toHaveBeenCalled()
    })

    it('reveals the actions when the message is tapped', async () => {
      const { container } = renderList([makeMessage({ id: 3 })])
      const row = container.querySelector('.chat-message') as HTMLElement
      expect(row).not.toHaveAttribute('data-active')
      await userEvent.click(screen.getByText('hello'))
      expect(row).toHaveAttribute('data-active')
    })
  })
})
