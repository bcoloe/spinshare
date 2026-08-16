import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
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
    it('renders a deleted message as a tombstone', () => {
      renderList([makeMessage({ is_deleted: true, body: '' })])
      expect(screen.getByText('[message deleted]')).toBeInTheDocument()
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

    it('hides delete on an already-deleted message', () => {
      renderList([makeMessage({ user_id: 1, is_deleted: true })], { canModerate: true })
      expect(screen.queryByLabelText('Delete message')).not.toBeInTheDocument()
    })
  })
})
