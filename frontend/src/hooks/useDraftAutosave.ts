import { useCallback, useEffect, useRef, useState, type FocusEvent } from 'react'
import type { UseMutationResult } from '@tanstack/react-query'
import { useAuth } from './useAuth'
import { albumService } from '../services/albumService'
import type { ReviewCreate, ReviewResponse, ReviewUpdate } from '../types/album'

/**
 * Autosave for a review draft that keeps the server out of the typing loop.
 *
 * Every server write wakes the database and invalidates cached pages for the whole
 * group, so drafts are saved to this device as you type (a second after the last
 * change) and sent to the server only when it matters:
 *
 *   - focus leaves the form (call `onBlur` from the form container),
 *   - the tab is hidden, or the page is closed (sent with `keepalive`),
 *   - the form unmounts (navigating away),
 *   - and at most once a minute during continuous editing.
 *
 * On return, a local draft newer than the server's copy is restored, so closing the
 * tab mid-sentence loses nothing even if the final flush didn't make it.
 */

export interface DraftContent {
  rating: number | null
  comment: string
}

interface StoredDraft extends DraftContent {
  savedAt: string
}

export type FlushResult = 'saved' | 'clean' | 'busy' | 'failed'

export const LOCAL_SAVE_DELAY_MS = 1000
export const SERVER_FLUSH_INTERVAL_MS = 60_000

export function draftStorageKey(userId: number, albumId: number): string {
  return `spinshare:review-draft:${userId}:${albumId}`
}

// Storage can be unavailable (private mode, quota, disabled). Autosave then
// degrades to server-only flushes rather than failing the form.
function readLocal(key: string): StoredDraft | null {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as StoredDraft) : null
  } catch {
    return null
  }
}

function writeLocal(key: string, draft: StoredDraft): void {
  try {
    localStorage.setItem(key, JSON.stringify(draft))
  } catch {
    // ignore: see readLocal
  }
}

function removeLocal(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch {
    // ignore: see readLocal
  }
}

function sameContent(a: DraftContent, b: DraftContent): boolean {
  return (a.rating ?? null) === (b.rating ?? null) && (a.comment ?? '') === (b.comment ?? '')
}

/** The local draft to restore over the server's copy, or null (dropping a stale one). */
function decideRestore(
  key: string,
  existingReview: ReviewResponse | null | undefined,
  published: boolean,
): DraftContent | null {
  const local = readLocal(key)
  if (!local) return null
  if (published) {
    removeLocal(key)
    return null
  }
  if (existingReview) {
    const serverTime = Date.parse(existingReview.updated_at ?? existingReview.reviewed_at)
    const serverContent = { rating: existingReview.rating, comment: existingReview.comment ?? '' }
    if (sameContent(local, serverContent) || serverTime >= Date.parse(local.savedAt)) {
      removeLocal(key)
      return null
    }
  }
  return { rating: local.rating, comment: local.comment }
}

interface Options {
  albumId: number
  groupId?: number
  /** The caller's review for this album: a draft, a published review, or none. */
  existingReview: ReviewResponse | null | undefined
  /** False until `existingReview` has loaded, so restore compares against the truth. */
  ready: boolean
  content: DraftContent
  /** Called once with a local draft that is newer than the server's. */
  onRestore: (content: DraftContent) => void
  submitReview: UseMutationResult<ReviewResponse, Error, ReviewCreate>
  updateReview: UseMutationResult<ReviewResponse, Error, { reviewId: number; data: ReviewUpdate }>
}

export function useDraftAutosave({
  albumId,
  groupId,
  existingReview,
  ready,
  content,
  onRestore,
  submitReview,
  updateReview,
}: Options) {
  const { user } = useAuth()
  const key = user ? draftStorageKey(user.id, albumId) : null
  const published = !!existingReview && !existingReview.is_draft
  const [savedAt, setSavedAt] = useState<Date | null>(null)

  // Refs so the handlers below can stay stable across renders and still see current
  // values. (Mutation results are new objects every render; depending on them would
  // re-run the unmount flush, and so flush to the server, on every keystroke.)
  const latest = useRef({ content, existingReview, published, key, submitReview, updateReview })
  latest.current = { content, existingReview, published, key, submitReview, updateReview }
  const dirty = useRef(false) // edited since the last server save
  const flushTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  // The local draft to restore: undefined until decided, null when there is none.
  const restoreTo = useRef<DraftContent | null | undefined>(undefined)
  const editedHere = useRef(false) // the user has typed since this form mounted

  /** Send the draft to the server if it changed. Resolves to what happened. */
  const flush = useCallback(
    async ({ keepalive = false }: { keepalive?: boolean } = {}): Promise<FlushResult> => {
      const { content: current, existingReview: review, published: isPublished, submitReview: submit, updateReview: update } =
        latest.current
      if (flushTimer.current) {
        clearTimeout(flushTimer.current)
        flushTimer.current = null
      }
      if (!dirty.current || isPublished) return 'clean'
      if (submit.isPending || update.isPending) return 'busy' // stays dirty; a later trigger retries
      dirty.current = false
      const data = {
        rating: current.rating ?? undefined,
        comment: current.comment || undefined,
        is_draft: true,
      }
      try {
        if (keepalive) {
          // The page is going away: send directly, without waiting on React state.
          await (review
            ? albumService.updateReview(albumId, review.id, data, groupId, { keepalive: true })
            : albumService.submitReview(albumId, data, groupId, { keepalive: true }))
        } else if (review) {
          await update.mutateAsync({ reviewId: review.id, data })
        } else {
          await submit.mutateAsync(data)
        }
        return 'saved'
      } catch {
        dirty.current = true // keep it for the next trigger; the local copy is safe meanwhile
        return 'failed'
      }
    },
    [albumId, groupId],
  )

  /** Call from the form's change handlers (user edits only, not prefills). */
  const markDirty = useCallback(() => {
    dirty.current = true
    editedHere.current = true
    if (!flushTimer.current) {
      flushTimer.current = setTimeout(() => {
        flushTimer.current = null
        void flush()
      }, SERVER_FLUSH_INTERVAL_MS)
    }
  }, [flush])

  /** Forget the local draft, e.g. once the review is published. */
  const clearLocal = useCallback(() => {
    dirty.current = false
    if (latest.current.key) removeLocal(latest.current.key)
  }, [])

  // Save to this device shortly after each edit.
  useEffect(() => {
    if (!key || published || !dirty.current) return
    const timer = setTimeout(() => {
      writeLocal(key, { ...content, savedAt: new Date().toISOString() })
      setSavedAt(new Date())
    }, LOCAL_SAVE_DELAY_MS)
    return () => clearTimeout(timer)
  }, [key, published, content.rating, content.comment]) // eslint-disable-line react-hooks/exhaustive-deps

  // Restore a newer local draft once the server's copy is known.
  //
  // The decision is made once; applying it is repeated each time this effect runs
  // until the user edits. The forms prefill from the server copy in their own
  // effect, and any remount (StrictMode does one in development) runs that prefill
  // again — a restore applied only once would be overwritten.
  useEffect(() => {
    if (!ready || !key) return
    if (restoreTo.current === undefined) restoreTo.current = decideRestore(key, existingReview, published)
    if (restoreTo.current && !editedHere.current) {
      onRestore(restoreTo.current)
      dirty.current = true // so it reaches the server on the next trigger
    }
  }, [ready, key, published, existingReview, onRestore])

  // Flush when the tab is hidden or the page is closed, and on unmount.
  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') void flush()
    }
    const onPageHide = () => void flush({ keepalive: true })
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('pagehide', onPageHide)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('pagehide', onPageHide)
      void flush()
    }
  }, [flush])

  /** Attach to the form container: flushes when focus leaves the form entirely. */
  const onBlur = useCallback(
    (event: FocusEvent<HTMLElement>) => {
      if (!event.currentTarget.contains(event.relatedTarget as Node | null)) void flush()
    },
    [flush],
  )

  return { markDirty, flush, clearLocal, onBlur, savedAt }
}
