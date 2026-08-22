import type { ReportableLink } from '../types/linkReport'

/**
 * Turn a stored album link value into an openable web URL.
 *
 * Three of the five links are stored as bare service IDs, so anything that wants
 * to *show* one — the admin review queue, the link editor's preview button — has
 * to rebuild the URL. Bandcamp and Wikipedia are already URLs and pass through.
 *
 * Accepts a full URL for the ID-based services too, so it can be pointed at a
 * raw `suggested_url` or at whatever an admin has currently typed into a field
 * without the caller having to know which form it is in.
 *
 * Returns null when there is nothing to link to.
 */
export function albumLinkUrl(link: ReportableLink, value: string | null | undefined): string | null {
  if (!value) return null
  const trimmed = value.trim()
  if (!trimmed) return null

  // Already a URL — the value was pasted rather than normalised, or the service
  // stores URLs natively.
  if (/^https?:\/\//i.test(trimmed)) return trimmed

  switch (link) {
    case 'spotify':
      return `https://open.spotify.com/album/${trimmed}`
    case 'apple_music':
      return `https://music.apple.com/album/${trimmed}`
    case 'youtube_music':
      // Browse IDs (MPREb_…) and playlist IDs (OLAK5uy_…) live at different paths;
      // the extractor returns either, so both have to be handled here.
      return trimmed.startsWith('OLAK5uy')
        ? `https://music.youtube.com/playlist?list=${trimmed}`
        : `https://music.youtube.com/browse/${trimmed}`
    case 'bandcamp':
    case 'wikipedia':
      // Stored as full URLs; a bare value here is not something we can resolve.
      return null
  }
}
