// Review drafts kept on this device by useDraftAutosave, keyed per user and album.

export interface StoredDraft {
  rating: number | null
  comment: string
  savedAt: string
  // The server copy this draft was edited on top of (its updated_at/reviewed_at),
  // or null when there was none. Restore compares server timestamps only, so a
  // skewed client clock can't make a stale draft win.
  baseServerTime: string | null
}

const STORAGE_PREFIX = 'spinshare:review-draft:'

export function draftStorageKey(userId: number, albumId: number): string {
  return `${STORAGE_PREFIX}${userId}:${albumId}`
}

// Storage can be unavailable (private mode, quota, disabled). Autosave then
// degrades to server-only flushes rather than failing the form.
export function readLocal(key: string): StoredDraft | null {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as StoredDraft) : null
  } catch {
    return null
  }
}

export function writeLocal(key: string, draft: StoredDraft): void {
  try {
    localStorage.setItem(key, JSON.stringify(draft))
  } catch {
    // ignore: see readLocal
  }
}

export function removeLocal(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch {
    // ignore: see readLocal
  }
}

/** Forget every local draft on this device, e.g. on logout from a shared browser. */
export function clearAllLocalDrafts(): void {
  try {
    Object.keys(localStorage)
      .filter((k) => k.startsWith(STORAGE_PREFIX))
      .forEach((k) => localStorage.removeItem(k))
  } catch {
    // ignore: see readLocal
  }
}
