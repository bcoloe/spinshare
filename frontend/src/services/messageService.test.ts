import { describe, it, expect, vi, beforeEach } from 'vitest'
import { messageService } from './messageService'
import { configureApiClient } from './apiClient'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function requestedUrl(): string {
  return mockFetch.mock.calls[0][0]
}

describe('messageService', () => {
  beforeEach(() => {
    mockFetch.mockReset()
    configureApiClient(() => 'token', vi.fn())
    mockFetch.mockResolvedValue(jsonResponse([]))
  })

  it('requests history with no params by default', async () => {
    await messageService.getMessages(7)
    expect(requestedUrl()).toBe('/api/groups/7/messages')
  })

  it('pages backwards with before', async () => {
    await messageService.getMessages(7, { before: 42 })
    expect(requestedUrl()).toBe('/api/groups/7/messages?before=42')
  })

  it('fetches only the delta with after', async () => {
    await messageService.getMessages(7, { after: 42 })
    expect(requestedUrl()).toBe('/api/groups/7/messages?after=42')
  })

  it('passes a limit through', async () => {
    await messageService.getMessages(7, { limit: 10 })
    expect(requestedUrl()).toBe('/api/groups/7/messages?limit=10')
  })

  it('omits params that were not supplied', async () => {
    await messageService.getMessages(7, { after: undefined, limit: 5 })
    expect(requestedUrl()).toBe('/api/groups/7/messages?limit=5')
  })

  it('posts a message body as JSON', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ id: 1 }))
    await messageService.postMessage(3, 'hello')

    expect(requestedUrl()).toBe('/api/groups/3/messages')
    expect(mockFetch.mock.calls[0][1].method).toBe('POST')
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({ body: 'hello' })
  })

  it('deletes by message id, not group id', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ id: 9 }))
    await messageService.deleteMessage(9)

    expect(requestedUrl()).toBe('/api/messages/9')
    expect(mockFetch.mock.calls[0][1].method).toBe('DELETE')
  })

  it('requests a socket ticket by POST', async () => {
    mockFetch.mockResolvedValue(jsonResponse({ ticket: 't', expires_in: 30 }))
    const result = await messageService.createTicket()

    expect(requestedUrl()).toBe('/api/chat/ticket')
    expect(mockFetch.mock.calls[0][1].method).toBe('POST')
    expect(result.ticket).toBe('t')
  })
})
