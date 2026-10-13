import { StrictMode, useCallback, useEffect, useState, type ReactNode } from 'react'
import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReviewResponse } from '../types/album'
import {
  LOCAL_SAVE_DELAY_MS,
  SERVER_FLUSH_INTERVAL_MS,
  draftStorageKey,
  useDraftAutosave,
  type DraftContent,
} from './useDraftAutosave'

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

function setup(opts: { existingReview?: ReviewResponse | null; ready?: boolean } = {}) {
  const submit = vi.fn().mockResolvedValue({})
  const update = vi.fn().mockResolvedValue({})
  const onRestore = vi.fn()
  const hook = renderHook(
    ({ content }: { content: DraftContent }) =>
      useDraftAutosave({
        albumId: ALBUM,
        existingReview: opts.existingReview ?? null,
        ready: opts.ready ?? true,
        content,
        onRestore,
        // Like useMutation: a new result object on every render.
        submitReview: { mutateAsync: submit, isPending: false } as never,
        updateReview: { mutateAsync: update, isPending: false } as never,
      }),
    { initialProps: { content: { rating: null, comment: '' } as DraftContent } },
  )
  /** What a change handler does: mark dirty, then update state. */
  const type = (content: DraftContent) => {
    act(() => hook.result.current.markDirty())
    hook.rerender({ content })
  }
  return {
    hook,
    type,
    onRestore,
    submit,
    update,
  }
}

beforeEach(() => {
  vi.useFakeTimers()
  localStorage.clear()
  vi.mocked(albumService.submitReview).mockReset().mockResolvedValue({} as never)
  vi.mocked(albumService.updateReview).mockReset().mockResolvedValue({} as never)
})

afterEach(() => {
  vi.useRealTimers()
})

describe('typing', () => {
  it('saves to this device, not the server', () => {
    const { type, submit } = setup()
    type({ rating: 7, comment: 'first thoughts' })

    act(() => vi.advanceTimersByTime(LOCAL_SAVE_DELAY_MS))

    expect(JSON.parse(localStorage.getItem(KEY)!)).toMatchObject({ rating: 7, comment: 'first thoughts' })
    expect(submit).not.toHaveBeenCalled()
  })

  it('reaches the server at most once a minute however long it goes on', async () => {
    const { type, submit } = setup()
    for (let i = 0; i < 30; i++) {
      type({ rating: 7, comment: `draft ${i}` })
      await act(async () => vi.advanceTimersByTime(3_000)) // a keystroke burst, then a pause
    }
    // 90 s of editing: one flush at the 60 s mark
    expect(submit).toHaveBeenCalledTimes(1)
  })

  it('a re-render without an edit does not flush', async () => {
    const { hook, submit } = setup()
    hook.rerender({ content: { rating: null, comment: '' } })
    await act(async () => vi.advanceTimersByTime(SERVER_FLUSH_INTERVAL_MS * 2))
    expect(submit).not.toHaveBeenCalled()
  })
})

describe('flush triggers', () => {
  it('focus leaving the form sends the draft once', async () => {
    const { hook, type, submit } = setup()
    type({ rating: 4, comment: 'meh' })
    const form = document.createElement('div')
    const outside = document.createElement('button')

    await act(async () => {
      hook.result.current.onBlur({ currentTarget: form, relatedTarget: outside } as never)
      hook.result.current.onBlur({ currentTarget: form, relatedTarget: outside } as never)
    })

    expect(submit).toHaveBeenCalledTimes(1)
    expect(submit).toHaveBeenCalledWith({ rating: 4, comment: 'meh', is_draft: true })
  })

  it('focus moving within the form does not', async () => {
    const { hook, type, submit } = setup()
    type({ rating: 4, comment: 'meh' })
    const form = document.createElement('div')
    const inside = document.createElement('textarea')
    form.appendChild(inside)

    await act(async () => hook.result.current.onBlur({ currentTarget: form, relatedTarget: inside } as never))

    expect(submit).not.toHaveBeenCalled()
  })

  it('hiding the tab sends the draft', async () => {
    const { type, update } = setup({ existingReview: review() })
    type({ rating: 9, comment: 'grew on me' })

    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
    await act(async () => document.dispatchEvent(new Event('visibilitychange')))

    expect(update).toHaveBeenCalledWith({ reviewId: 5, data: { rating: 9, comment: 'grew on me', is_draft: true } })
  })

  it('closing the page sends it with keepalive', async () => {
    const { type } = setup({ existingReview: review() })
    type({ rating: 9, comment: 'last words' })

    await act(async () => window.dispatchEvent(new Event('pagehide')))

    expect(albumService.updateReview).toHaveBeenCalledWith(
      ALBUM, 5, { rating: 9, comment: 'last words', is_draft: true }, undefined, { keepalive: true },
    )
  })

  it('unmounting sends the draft', async () => {
    const { hook, type, submit } = setup()
    type({ rating: 3, comment: 'leaving' })
    await act(async () => hook.unmount())
    expect(submit).toHaveBeenCalledTimes(1)
  })

  it('a failed send is retried by the next trigger', async () => {
    const { hook, type, submit } = setup()
    submit.mockRejectedValueOnce(new Error('offline'))
    type({ rating: 3, comment: 'retry me' })

    expect(await act(async () => hook.result.current.flush())).toBe('failed')
    expect(await act(async () => hook.result.current.flush())).toBe('saved')
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

describe('restoring', () => {
  const stored = (savedAt: string, comment = 'local copy') =>
    localStorage.setItem(KEY, JSON.stringify({ rating: 8, comment, savedAt }))

  it('restores a local draft newer than the server copy, and syncs it', async () => {
    stored('2026-10-12T11:00:00Z')
    const { hook, onRestore, update } = setup({ existingReview: review() })

    expect(onRestore).toHaveBeenCalledWith({ rating: 8, comment: 'local copy' })
    await act(async () => hook.result.current.flush())
    expect(update).toHaveBeenCalledTimes(1)
  })

  it('the restored draft wins over the form prefilling from the server, even under StrictMode', () => {
    // The real forms prefill from the server copy in their own effect, and dev
    // builds run every effect twice (mount, unmount, mount).
    stored('2026-10-12T11:00:00Z')
    const server = review()
    const { result } = renderHook(
      () => {
        const [content, setContent] = useState<DraftContent>({ rating: null, comment: '' })
        useEffect(() => {
          setContent({ rating: server.rating, comment: server.comment ?? '' })
        }, [server.id])
        const onRestore = useCallback((d: DraftContent) => setContent(d), [])
        useDraftAutosave({
          albumId: ALBUM, existingReview: server, ready: true, content, onRestore,
          submitReview: { mutateAsync: vi.fn(), isPending: false } as never,
          updateReview: { mutateAsync: vi.fn().mockResolvedValue({}), isPending: false } as never,
        })
        return content
      },
      { wrapper: ({ children }: { children: ReactNode }) => <StrictMode>{children}</StrictMode> },
    )
    expect(result.current).toEqual({ rating: 8, comment: 'local copy' })
  })

  it('never re-applies the restore over later edits', () => {
    stored('2026-10-12T11:00:00Z')
    const { hook, type, onRestore } = setup({ existingReview: review() })
    expect(onRestore).toHaveBeenCalledTimes(1)

    type({ rating: 8, comment: 'kept typing' })
    hook.rerender({ content: { rating: 8, comment: 'kept typing' } })

    expect(onRestore).toHaveBeenCalledTimes(1)
  })

  it('restores a local draft when the server has none', () => {
    stored('2026-10-12T11:00:00Z')
    const { onRestore } = setup({ existingReview: null })
    expect(onRestore).toHaveBeenCalledTimes(1)
  })

  it('drops a local draft older than the server copy', () => {
    stored('2026-10-12T09:00:00Z')
    const { onRestore } = setup({ existingReview: review() })
    expect(onRestore).not.toHaveBeenCalled()
    expect(localStorage.getItem(KEY)).toBeNull()
  })

  it('drops a local draft once the review is published', () => {
    stored('2026-10-12T11:00:00Z')
    const { onRestore } = setup({ existingReview: review({ is_draft: false }) })
    expect(onRestore).not.toHaveBeenCalled()
    expect(localStorage.getItem(KEY)).toBeNull()
  })

  it('waits until the server copy has loaded', () => {
    stored('2026-10-12T11:00:00Z')
    const { onRestore } = setup({ ready: false })
    expect(onRestore).not.toHaveBeenCalled()
  })

  it('clearLocal forgets the draft', () => {
    stored('2026-10-12T11:00:00Z')
    const { hook } = setup({ existingReview: review({ is_draft: false }) })
    act(() => hook.result.current.clearLocal())
    expect(localStorage.getItem(KEY)).toBeNull()
  })
})
