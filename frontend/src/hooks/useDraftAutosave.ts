import { useCallback, useEffect, useRef, useState, type FocusEvent } from 'react'
import { useQueryClient, type UseMutationResult } from '@tanstack/react-query'
import { useAuth } from './useAuth'
import { applyDraftToCache } from './useDailySpin'
import { albumService } from '../services/albumService'
import { draftStorageKey, readLocal, removeLocal, writeLocal } from '../utils/draftStorage'
import type { ReviewCreate, ReviewResponse, ReviewUpdate } from '../types/album'

/**
 * Autosave for a review draft that keeps the server out of the typing loop.
 *
 * Every server write wakes the database and invalidates cached pages for the whole
 * group. So drafts are written to this device on every edit, and sent to the server
 * only when it matters:
 *
 *   - focus leaves the form (attach `onBlur` to the form container),
 *   - the tab is hidden or the page is closed (sent with `keepalive`),
 *   - the form unmounts (navigating away within the app),
 *   - and at most once a minute during continuous editing.
 *
 * The hook is also the only thing that sets the form's starting content: the
 * server's draft, or a local one that is newer. Forms must not prefill drafts
 * themselves — a second writer is how typing gets overwritten (for instance when
 * the first save turns "no review" into a draft and changes its id).
 */

export interface DraftContent {
  rating: number | null
  comment: string
}


export type FlushResult = 'saved' | 'clean' | 'busy' | 'failed'

export const SERVER_FLUSH_INTERVAL_MS = 60_000

function serverTime(review: ReviewResponse | null | undefined): string | null {
  return review ? (review.updated_at ?? review.reviewed_at) : null
}

function sameInstant(a: string | null, b: string | null): boolean {
  return a === b || (a !== null && b !== null && Date.parse(a) === Date.parse(b))
}

function sameContent(a: DraftContent, b: DraftContent): boolean {
  return (a.rating ?? null) === (b.rating ?? null) && (a.comment ?? '') === (b.comment ?? '')
}

/**
 * Where an unpublished form should start: the content to load (null for an empty
 * form), and whether it still needs to reach the server.
 */
function startingContent(key: string, review: ReviewResponse | null | undefined): {
  content: DraftContent | null
  unsynced: boolean
} {
  const server = review ? { rating: review.rating, comment: review.comment ?? '' } : null
  const local = readLocal(key)
  if (!local) return { content: server, unsynced: false }
  const localContent = { rating: local.rating, comment: local.comment }
  if (server && sameContent(localContent, server)) {
    removeLocal(key) // already saved
    return { content: server, unsynced: false }
  }
  if (server && !sameInstant(serverTime(review), local.baseServerTime)) {
    removeLocal(key) // the server copy changed after this draft was based on it
    return { content: server, unsynced: false }
  }
  return { content: localContent, unsynced: true }
}

interface Options {
  albumId: number
  groupId?: number
  /** The caller's review for this album: a draft, a published review, or none. */
  existingReview: ReviewResponse | null | undefined
  /** True once `existingReview` is known (loaded successfully), not merely not loading. */
  ready: boolean
  content: DraftContent
  /** Sets the form's content. Called once, with the draft to start from. */
  onLoad: (content: DraftContent) => void
  submitReview: UseMutationResult<ReviewResponse, Error, ReviewCreate>
  updateReview: UseMutationResult<ReviewResponse, Error, { reviewId: number; data: ReviewUpdate }>
}

export function useDraftAutosave({
  albumId,
  groupId,
  existingReview,
  ready,
  content,
  onLoad,
  submitReview,
  updateReview,
}: Options) {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const key = user ? draftStorageKey(user.id, albumId) : null
  const published = !!existingReview && !existingReview.is_draft
  const [savedAt, setSavedAt] = useState<Date | null>(null)

  // Refs so the handlers below can stay stable across renders and still see current
  // values. (Mutation results are new objects every render; depending on them would
  // re-run the unmount flush, and so flush to the server, on every keystroke.)
  const latest = useRef({ content, existingReview, published, key, submitReview, updateReview })
  latest.current = { content, existingReview, published, key, submitReview, updateReview }
  const dirty = useRef(false) // edited since the last server save
  const editedHere = useRef(false) // the user has typed since this form mounted
  const loaded = useRef(false)
  const inFlight = useRef(false)
  // The draft this hook last saved. Until the cache's copy catches up, it tells the
  // next save to update that draft rather than create a second one.
  const lastSaved = useRef<ReviewResponse | null>(null)
  const flushTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const saveLocal = useCallback(() => {
    const { key: storageKey, content: current, existingReview: review, published: isPublished } = latest.current
    if (!storageKey || isPublished || !editedHere.current) return
    writeLocal(storageKey, {
      ...current,
      savedAt: new Date().toISOString(),
      baseServerTime: serverTime(review ?? lastSaved.current),
    })
  }, [])

  /** Send the draft to the server if it changed. Resolves to what happened. */
  const flush = useCallback(
    async ({ keepalive = false }: { keepalive?: boolean } = {}): Promise<FlushResult> => {
      const { content: current, existingReview: cached, published: isPublished, submitReview: submit, updateReview: update } =
        latest.current
      if (flushTimer.current) {
        clearTimeout(flushTimer.current)
        flushTimer.current = null
      }
      if (!dirty.current || isPublished) return 'clean'
      // A keepalive send isn't tracked by the mutations, so guard in-flight saves here:
      // two concurrent creates would race into a 409.
      if (inFlight.current || submit.isPending || update.isPending) return 'busy'
      saveLocal() // the device copy must hold everything being sent, in case this fails
      dirty.current = false
      inFlight.current = true
      const review = cached ?? lastSaved.current
      const data = {
        rating: current.rating ?? undefined,
        comment: current.comment || undefined,
        is_draft: true,
      }
      try {
        let saved: ReviewResponse
        if (keepalive) {
          // The page may be going away: send directly so the request outlives it.
          saved = await (review
            ? albumService.updateReview(albumId, review.id, data, groupId, { keepalive: true })
            : albumService.submitReview(albumId, data, groupId, { keepalive: true }))
          // If the page survives (hidden tab, back/forward cache), keep the cache right.
          applyDraftToCache(queryClient, albumId, saved)
        } else if (review) {
          saved = await update.mutateAsync({ reviewId: review.id, data })
        } else {
          saved = await submit.mutateAsync(data)
        }
        lastSaved.current = saved
        return 'saved'
      } catch {
        dirty.current = true // keep it for the next trigger; the local copy is safe meanwhile
        return 'failed'
      } finally {
        inFlight.current = false
      }
    },
    [albumId, groupId, queryClient, saveLocal],
  )

  /** Call from the form's change handlers (user edits only). */
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
    editedHere.current = false
    if (latest.current.key) removeLocal(latest.current.key)
  }, [])

  // Write to this device on every edit. Cheap (a comment is at most 5,000 chars),
  // and it means nothing typed is ever only in memory.
  useEffect(() => {
    if (!editedHere.current) return
    saveLocal()
    setSavedAt(new Date())
  }, [content.rating, content.comment, saveLocal])

  // Decide the starting content once the server's copy is known.
  useEffect(() => {
    if (loaded.current || !ready || !key) return
    loaded.current = true
    if (published) {
      removeLocal(key)
      return
    }
    const start = startingContent(key, existingReview)
    if (!start.content) return
    // Set the ref too: a flush before the next render (StrictMode's simulated
    // unmount does one) must send what the form is about to show.
    latest.current.content = start.content
    onLoad(start.content)
    if (start.unsynced) dirty.current = true
  }, [ready, key, published, existingReview, onLoad])

  // Flush when the tab is hidden or the page is closed, and on unmount.
  useEffect(() => {
    // Hidden comes before pagehide and may be the last chance, so it uses keepalive too.
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') void flush({ keepalive: true })
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
