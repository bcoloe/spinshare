import { StrictMode, useCallback, useState, type ReactNode } from 'react'
import { act, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReviewResponse } from '../types/album'
import { clearAllLocalDrafts, draftStorageKey } from '../utils/draftStorage'
import { SERVER_FLUSH_INTERVAL_MS, useDraftAutosave, type DraftContent } from './useDraftAutosave'

vi.mock('./useAuth', () => ({ useAuth: () => ({ user: { id: 7 } }) }))
vi.mock('../services/albumService', () => ({
  albumService: { submitReview: vi.fn(), updateReview: vi.fn() },
}))

import { albumService } from '../services/albumService'

const ALBUM = 42
const KEY = draftStorageKey(7, ALBUM)

function review(overrides: Partial<ReviewResponse> = {}): ReviewResponse {
  return {
    id: 5,
    album_id: ALBUM,
    user_id: 7,
    rating: 6,
    comment: 'server copy',
    is_draft: true,
    reviewed_at: '2026-10-12T10:00:00Z',
    updated_at: null,
    ...overrides,
  } as ReviewResponse
}

function stored(content: Partial<DraftContent> & { baseServerTime: string | null; savedAt?: string }) {
  localStorage.setItem(KEY, JSON.stringify({ rating: 8, comment: 'local copy', savedAt: '2026-10-12T11:00:00Z', ...content }))
}

const local = () => JSON.parse(localStorage.getItem(KEY) ?? 'null')

/**
 * The hook inside a form-like component: it owns the content state, and — like the
 * real forms — does not prefill drafts itself. Mutation results are rebuilt every
 * render, as useMutation's are.
 */
function setup(opts: { existingReview?: ReviewResponse | null; ready?: boolean; strict?: boolean } = {}) {
  const submit = vi.fn().mockImplementation(async (data) => review({ id: 99, ...data, updated_at: '2026-10-12T12:00:00Z' }))
  const update = vi.fn().mockImplementation(async ({ reviewId, data }) =>
    review({ id: reviewId, ...data, updated_at: '2026-10-12T12:00:00Z' }))
  const onLoad = vi.fn()
  const queryClient = new QueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => {
    const tree = <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    return opts.strict ? <StrictMode>{tree}</StrictMode> : tree
  }
  const hook = renderHook(
    ({ existingReview, ready }: { existingReview: ReviewResponse | null; ready: boolean }) => {
      const [content, setContent] = useState<DraftContent>({ rating: null, comment: '' })
      const load = useCallback((d: DraftContent) => {
        onLoad(d)
        setContent(d)
      }, [])
      const autosave = useDraftAutosave({
        albumId: ALBUM,
        existingReview,
        ready,
        content,
        onLoad: load,
        submitReview: { mutateAsync: submit, isPending: false } as never,
        updateReview: { mutateAsync: update, isPending: false } as never,
      })
      return { autosave, content, setContent }
    },
    { wrapper, initialProps: { existingReview: opts.existingReview ?? null, ready: opts.ready ?? true } },
  )
  /** What a change handler does: mark dirty, then update state. */
  const type = (content: DraftContent) =>
    act(() => {
      hook.result.current.autosave.markDirty()
      hook.result.current.setContent(content)
    })
  const flush = (o?: { keepalive?: boolean }) => act(() => hook.result.current.autosave.flush(o))
  return { hook, type, flush, onLoad, submit, update, queryClient }
}

beforeEach(() => {
  vi.useFakeTimers()
  localStorage.clear()
  vi.mocked(albumService.submitReview).mockReset().mockResolvedValue(review({ id: 77 }))
  vi.mocked(albumService.updateReview).mockReset().mockResolvedValue(review())
})

afterEach(() => {
  vi.useRealTimers()
})

describe('typing', () => {
  it('is written to this device straight away, not sent to the server', () => {
    const { type, submit } = setup()
    type({ rating: 7, comment: 'first thoughts' })

    expect(local()).toMatchObject({ rating: 7, comment: 'first thoughts', baseServerTime: null })
    expect(submit).not.toHaveBeenCalled()
  })

  it('reaches the server at most once a minute however long it goes on', async () => {
    const { type, submit } = setup()
    for (let i = 0; i < 30; i++) {
      type({ rating: 7, comment: `draft ${i}` })
      await act(async () => vi.advanceTimersByTime(3_000))
    }
    expect(submit).toHaveBeenCalledTimes(1) // 90 s of editing: one flush at 60 s
    expect(SERVER_FLUSH_INTERVAL_MS).toBe(60_000)
  })

  it('a re-render without an edit does not flush', async () => {
    const { hook, submit } = setup()
    hook.rerender({ existingReview: null, ready: true })
    await act(async () => vi.advanceTimersByTime(SERVER_FLUSH_INTERVAL_MS * 2))
    expect(submit).not.toHaveBeenCalled()
  })
})

describe('flush triggers', () => {
  const form = () => {
    const el = document.createElement('div')
    const inside = document.createElement('textarea')
    el.appendChild(inside)
    return { el, inside, outside: document.createElement('button') }
  }

  it('focus leaving the form sends the draft once', async () => {
    const { hook, type, submit } = setup()
    type({ rating: 4, comment: 'meh' })
    const { el, outside } = form()
    await act(async () => {
      hook.result.current.autosave.onBlur({ currentTarget: el, relatedTarget: outside } as never)
      hook.result.current.autosave.onBlur({ currentTarget: el, relatedTarget: outside } as never)
    })
    expect(submit).toHaveBeenCalledTimes(1)
    expect(submit).toHaveBeenCalledWith({ rating: 4, comment: 'meh', is_draft: true })
  })

  it('focus moving within the form does not', async () => {
    const { hook, type, submit } = setup()
    type({ rating: 4, comment: 'meh' })
    const { el, inside } = form()
    await act(async () => hook.result.current.autosave.onBlur({ currentTarget: el, relatedTarget: inside } as never))
    expect(submit).not.toHaveBeenCalled()
  })

  it('hiding the tab sends with keepalive (it may be the last chance) and updates the cache', async () => {
    const { type, queryClient } = setup({ existingReview: review() })
    type({ rating: 9, comment: 'grew on me' })

    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
    await act(async () => document.dispatchEvent(new Event('visibilitychange')))

    expect(albumService.updateReview).toHaveBeenCalledWith(
      ALBUM, 5, { rating: 9, comment: 'grew on me', is_draft: true }, undefined, { keepalive: true },
    )
    expect(queryClient.getQueryData(['reviews', ALBUM, 'me'])).toMatchObject({ id: 5 })
  })

  it('closing the page sends with keepalive; nothing is sent twice', async () => {
    const { type } = setup({ existingReview: review() })
    type({ rating: 9, comment: 'last words' })

    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'))
      window.dispatchEvent(new Event('pagehide'))
    })

    expect(albumService.updateReview).toHaveBeenCalledTimes(1)
  })

  it('unmounting sends the draft', async () => {
    const { hook, type, submit } = setup()
    type({ rating: 3, comment: 'leaving' })
    await act(async () => hook.unmount())
    expect(submit).toHaveBeenCalledTimes(1)
  })

  it('a failed send keeps everything on the device and is retried by the next trigger', async () => {
    const { type, flush, submit } = setup()
    submit.mockRejectedValueOnce(new Error('offline'))
    type({ rating: 3, comment: 'retry me' })

    expect(await flush()).toBe('failed')
    expect(local()).toMatchObject({ comment: 'retry me' })
    expect(await flush()).toBe('saved')
    expect(submit).toHaveBeenCalledTimes(2)
  })

  it('a published review is never autosaved', async () => {
    const { hook, type, update, submit } = setup({ existingReview: review({ is_draft: false }) })
    type({ rating: 1, comment: 'editing' })
    await act(async () => hook.unmount())
    expect(update).not.toHaveBeenCalled()
    expect(submit).not.toHaveBeenCalled()
  })
})

describe('creating, then updating, the draft', () => {
  it('the first save creates it and later saves update it, even before the cache catches up', async () => {
    const { type, flush, submit, update } = setup()
    type({ rating: 5, comment: 'one' })
    await flush()
    type({ rating: 5, comment: 'one two' })
    await flush() // existingReview prop still null here

    expect(submit).toHaveBeenCalledTimes(1)
    expect(update).toHaveBeenCalledWith({ reviewId: 99, data: { rating: 5, comment: 'one two', is_draft: true } })
  })

  it('a save in flight blocks a second create (no duplicate draft)', async () => {
    let finish: (r: ReviewResponse) => void = () => {}
    vi.mocked(albumService.submitReview).mockImplementation(() => new Promise((resolve) => { finish = resolve }))
    const { hook, type, submit } = setup()
    type({ rating: 5, comment: 'racing' })

    let first: Promise<unknown> = Promise.resolve()
    act(() => { first = hook.result.current.autosave.flush({ keepalive: true }) })
    type({ rating: 5, comment: 'racing on' })
    const second = await act(() => hook.result.current.autosave.flush())

    expect(second).toBe('busy')
    expect(submit).not.toHaveBeenCalled()
    await act(async () => { finish(review({ id: 77 })); await first })
  })

  it('typing is not overwritten when the draft is created and the review changes identity', async () => {
    const { hook, type, flush } = setup()
    type({ rating: 5, comment: 'typed before the save' })
    await flush()
    type({ rating: 5, comment: 'typed while it was in flight' })

    hook.rerender({ existingReview: review({ id: 99, comment: 'typed before the save' }), ready: true })

    expect(hook.result.current.content.comment).toBe('typed while it was in flight')
  })

  it('edits made while a save is in flight are sent once it lands, even if the last trigger found it busy', async () => {
    let finish: (r: ReviewResponse) => void = () => {}
    const { hook, type, update } = setup({ existingReview: review() })
    update.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    type({ rating: 6, comment: 'first' })
    act(() => { void hook.result.current.autosave.flush() }) // slow save in flight
    type({ rating: 6, comment: 'first and more' })

    expect(await act(() => hook.result.current.autosave.flush())).toBe('busy') // e.g. blur
    await act(async () => { hook.unmount() }) // the last trigger: also busy

    await act(async () => { finish(review({ comment: 'first', updated_at: '2026-10-12T12:00:00Z' })) })
    await act(async () => { await Promise.resolve() })

    expect(update).toHaveBeenCalledTimes(2)
    expect(update.mock.calls[1][0].data.comment).toBe('first and more')
    // And the device copy sits on the version just saved, so it stays restorable.
    expect(local()).toMatchObject({ comment: 'first and more' })
    expect(local().baseServerTime).not.toBe('2026-10-12T10:00:00Z')
  })

  it('a save that returns a new review object does not trigger another save', async () => {
    const { hook, type, flush, update } = setup({ existingReview: review() })
    type({ rating: 6, comment: 'edit' })
    await flush()
    hook.rerender({ existingReview: review({ comment: 'edit', updated_at: '2026-10-12T12:00:00Z' }), ready: true })

    expect(await flush()).toBe('clean')
    await act(async () => hook.unmount())
    expect(update).toHaveBeenCalledTimes(1)
  })
})

describe('starting content', () => {
  it('loads the server draft once', () => {
    const { hook, onLoad } = setup({ existingReview: review() })
    hook.rerender({ existingReview: review({ comment: 'changed elsewhere', updated_at: '2026-10-12T13:00:00Z' }), ready: true })
    expect(onLoad).toHaveBeenCalledTimes(1)
    expect(onLoad).toHaveBeenCalledWith({ rating: 6, comment: 'server copy' })
  })

  it('restores a local draft edited on top of the current server copy, and syncs it', async () => {
    stored({ baseServerTime: '2026-10-12T10:00:00Z' })
    const { flush, onLoad, update } = setup({ existingReview: review() })

    expect(onLoad).toHaveBeenCalledWith({ rating: 8, comment: 'local copy' })
    await flush()
    expect(update).toHaveBeenCalledWith({ reviewId: 5, data: { rating: 8, comment: 'local copy', is_draft: true } })
  })

  it('restores a local draft when the server has none', () => {
    stored({ baseServerTime: null })
    const { onLoad } = setup({ existingReview: null })
    expect(onLoad).toHaveBeenCalledWith({ rating: 8, comment: 'local copy' })
  })

  it('drops a local draft once the server copy has moved on, whatever the client clock says', () => {
    // savedAt is far in the future (a skewed clock); only server timestamps decide.
    stored({ baseServerTime: '2026-10-12T09:00:00Z', savedAt: '2099-01-01T00:00:00Z' })
    const { onLoad } = setup({ existingReview: review() })
    expect(onLoad).toHaveBeenCalledWith({ rating: 6, comment: 'server copy' })
    expect(local()).toBeNull()
  })

  it('drops a local draft that matches the server copy', () => {
    stored({ baseServerTime: null, rating: 6, comment: 'server copy' })
    const { onLoad } = setup({ existingReview: review() })
    expect(onLoad).toHaveBeenCalledWith({ rating: 6, comment: 'server copy' })
    expect(local()).toBeNull()
  })

  it('drops a local draft once the review is published', () => {
    stored({ baseServerTime: '2026-10-12T10:00:00Z' })
    const { onLoad } = setup({ existingReview: review({ is_draft: false }) })
    expect(onLoad).not.toHaveBeenCalled()
    expect(local()).toBeNull()
  })

  it('typing done before the review loaded is not replaced when it does', () => {
    const { hook, type, onLoad } = setup({ ready: false })
    type({ rating: 4, comment: 'typed while the review was still loading' })

    hook.rerender({ existingReview: review(), ready: true })

    expect(onLoad).not.toHaveBeenCalled()
    expect(hook.result.current.content.comment).toBe('typed while the review was still loading')
    expect(local()).toMatchObject({ comment: 'typed while the review was still loading' })
  })

  it('waits until the server copy has loaded', () => {
    stored({ baseServerTime: null })
    const { onLoad } = setup({ ready: false })
    expect(onLoad).not.toHaveBeenCalled()
    expect(local()).not.toBeNull()
  })

  it('under StrictMode, the restored draft is what the form shows and what gets sent', async () => {
    stored({ baseServerTime: '2026-10-12T10:00:00Z' })
    const { hook, update } = setup({ existingReview: review(), strict: true })

    expect(hook.result.current.content).toEqual({ rating: 8, comment: 'local copy' })
    expect(update).toHaveBeenCalled() // StrictMode's simulated unmount flushes; the loop below must have something to check
    for (const call of update.mock.calls) {
      expect(call[0].data).toMatchObject({ comment: 'local copy' }) // never the pre-restore content
    }
  })
})

describe('clearing', () => {
  it('clearLocal forgets this draft', () => {
    stored({ baseServerTime: '2026-10-12T10:00:00Z' })
    const { hook } = setup({ existingReview: review() })
    expect(local()).not.toBeNull()

    act(() => hook.result.current.autosave.clearLocal())

    expect(local()).toBeNull()
  })

  it('clearAllLocalDrafts removes every draft and nothing else', () => {
    localStorage.setItem(draftStorageKey(1, 2), '{}')
    localStorage.setItem(draftStorageKey(3, 4), '{}')
    localStorage.setItem('refresh_token', 'keep')

    clearAllLocalDrafts()

    expect(Object.keys(localStorage)).toEqual(['refresh_token'])
  })
})
