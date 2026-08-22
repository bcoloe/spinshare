/** Which of an album's links a report is about. Mirrors ReportableLink on the backend. */
export type ReportableLink =
  | 'spotify'
  | 'apple_music'
  | 'youtube_music'
  | 'bandcamp'
  | 'wikipedia'

export type LinkReportStatus = 'open' | 'resolved' | 'dismissed'

/** Why a link is being reported. Free text is optional detail on top of this. */
export type ReportReason = 'missing' | 'bad' | 'other'

/** Compact labels for the admin queue, where the column is narrow. */
export const REASON_LABELS: Record<ReportReason, string> = {
  missing: 'Missing',
  bad: 'Broken',
  other: 'Other',
}

/** Longer wording for the report form, where there is room to be explicit. */
export const REASON_OPTIONS: { value: ReportReason; label: string; hint: string }[] = [
  { value: 'missing', label: 'Missing', hint: 'There is no link here, but there should be' },
  { value: 'bad', label: 'Wrong or broken', hint: 'The link is dead or points at the wrong album' },
  { value: 'other', label: 'Something else', hint: 'Tell us what is wrong' },
]

/** Album links are flat columns, so a report names the column it targets. */
export const LINK_FIELD_TO_COLUMN: Record<ReportableLink, string> = {
  spotify: 'spotify_album_id',
  apple_music: 'apple_music_album_id',
  youtube_music: 'youtube_music_id',
  bandcamp: 'artist_url',
  wikipedia: 'wikipedia_url',
}

export const LINK_LABELS: Record<ReportableLink, string> = {
  spotify: 'Spotify',
  apple_music: 'Apple Music',
  youtube_music: 'YouTube Music',
  bandcamp: 'Bandcamp',
  wikipedia: 'Wikipedia',
}

export interface LinkReportCreate {
  link_field: ReportableLink
  reason_code: ReportReason
  reason_detail?: string | null
  suggested_url?: string | null
}

export interface LinkReportResponse {
  id: number
  album_id: number
  reporter_id: number | null
  link_field: ReportableLink
  reason_code: ReportReason
  reason_detail: string | null
  suggested_url: string | null
  suggested_value: string | null
  status: LinkReportStatus
  resolved_by: number | null
  resolved_at: string | null
  resolution_note: string | null
  created_at: string
}

export interface AlbumLinksSnapshot {
  id: number
  title: string
  artist: string
  cover_url: string | null
  spotify_album_id: string | null
  apple_music_album_id: string | null
  youtube_music_id: string | null
  artist_url: string | null
  wikipedia_url: string | null
}

export interface AdminLinkReportItem extends LinkReportResponse {
  album: AlbumLinksSnapshot
  reporter_username: string | null
  current_value: string | null
}
