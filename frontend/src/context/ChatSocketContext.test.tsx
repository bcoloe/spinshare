import type { ReactNode } from 'react'
import { act, render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ChatSocketProvider } from './ChatSocketContext'

// One stable object, because the provider's connect effect keys off `user`
// identity. AuthContext holds it in state, so it only changes on a real login or
// logout; a mock that returned a fresh literal per render would tear the socket
// down and rebuild it on every state update.
const USER = { id: 1, username: 'alice' }

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({ user: USER }),
}))

vi.mock('../services/messageService', () => ({
  messageService: {
    createTicket: vi.fn().mockResolvedValue({ ticket: 'ticket-abc' }),
    getUnreadCounts: vi.fn().mockResolvedValue({}),
  },
}))

/** Minimal stand-in for the browser WebSocket, driven by the test. */
class FakeSocket {
  static instances: FakeSocket[] = []

  onopen: (() => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onerror: (() => void) | null = null

  constructor(public url: string) {
    FakeSocket.instances.push(this)
  }

  close() {}

  /** The server accepted the handshake. */
  open() {
    this.onopen?.()
  }

  /** The connection dropped. 1006 is what an abnormal close looks like. */
  die(code = 1006) {
    this.onclose?.({ code })
  }
}

function Harness({ children }: { children?: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return (
    <QueryClientProvider client={queryClient}>
      <ChatSocketProvider>{children}</ChatSocketProvider>
    </QueryClientProvider>
  )
}

/** Let the ticket promise settle so the socket constructor runs. */
async function flush() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
}

async function advance(ms: number) {
  await act(async () => {
    vi.advanceTimersByTime(ms)
  })
  await flush()
}

const STABLE_AFTER_MS = 30_000
const MAX_RETRY_MS = 30_000
// Backoff is jittered to 0.5–1.0x, so at the ceiling the shortest possible wait
// is 15s and at the base the longest possible wait is 1s. Every assertion below
// is written against those bounds rather than an exact delay.
const BASE_RETRY_CEILING_MS = 1000

/** Open the newest socket, then drop it before it can prove stable. */
async function flap() {
  const socket = FakeSocket.instances[FakeSocket.instances.length - 1]
  await act(async () => {
    socket.open()
  })
  await act(async () => {
    socket.die()
  })
}

describe('ChatSocketProvider backoff', () => {
  beforeEach(() => {
    // Fake only the two timer functions the provider uses, and let the clock
    // keep advancing with real time. Faking everything stalls React's scheduler
    // and a frozen clock deadlocks Testing Library's async `act`, which waits on
    // a real setTimeout of its own. Real elapsed time is a few milliseconds per
    // test, far below the second-scale margins every assertion here relies on.
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'], shouldAdvanceTime: true })
    FakeSocket.instances = []
    vi.stubGlobal('WebSocket', FakeSocket)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('backs off when a socket opens and dies before proving stable', async () => {
    render(<Harness />)
    await flush()
    expect(FakeSocket.instances).toHaveLength(1)

    // Five open-then-immediately-die cycles. Each advance clears the ceiling so
    // the next attempt is made, and also runs past STABLE_AFTER_MS — which is
    // what proves the stability timer is cancelled on close rather than firing
    // late and forgiving the backoff anyway.
    for (let cycle = 0; cycle < 5; cycle += 1) {
      await flap()
      await advance(MAX_RETRY_MS)
    }

    const attemptsSoFar = FakeSocket.instances.length
    await flap()

    // The counter has climbed, so the next wait is 15-30s. A second is nowhere
    // near enough. Before this fix it would have been, forever.
    await advance(BASE_RETRY_CEILING_MS)
    expect(FakeSocket.instances).toHaveLength(attemptsSoFar)
  })

  it('forgives the backoff once a connection has lasted', async () => {
    render(<Harness />)
    await flush()

    for (let cycle = 0; cycle < 5; cycle += 1) {
      await flap()
      await advance(MAX_RETRY_MS)
    }

    // This one survives the stability threshold before dropping.
    const survivor = FakeSocket.instances[FakeSocket.instances.length - 1]
    await act(async () => {
      survivor.open()
    })
    await advance(STABLE_AFTER_MS)

    const attemptsSoFar = FakeSocket.instances.length
    await act(async () => {
      survivor.die()
    })

    // Backoff is back to base, so a second is guaranteed to cover it.
    await advance(BASE_RETRY_CEILING_MS)
    expect(FakeSocket.instances).toHaveLength(attemptsSoFar + 1)
  })

  it('reconnects promptly the first time a healthy socket drops', async () => {
    render(<Harness />)
    await flush()

    const socket = FakeSocket.instances[0]
    await act(async () => {
      socket.open()
    })
    await advance(STABLE_AFTER_MS)
    await act(async () => {
      socket.die()
    })

    await advance(BASE_RETRY_CEILING_MS)
    expect(FakeSocket.instances).toHaveLength(2)
  })
})
