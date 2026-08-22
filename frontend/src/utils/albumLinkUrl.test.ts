import { describe, it, expect } from 'vitest'
import { albumLinkUrl } from './albumLinkUrl'

describe('albumLinkUrl', () => {
  it('builds a Spotify album URL from a bare ID', () => {
    expect(albumLinkUrl('spotify', '3v1nspBDZhlcJGDW6fUJQR')).toBe(
      'https://open.spotify.com/album/3v1nspBDZhlcJGDW6fUJQR',
    )
  })

  it('builds an Apple Music URL from a bare ID', () => {
    expect(albumLinkUrl('apple_music', '1097862703')).toBe(
      'https://music.apple.com/album/1097862703',
    )
  })

  it('sends a YouTube Music browse ID to /browse', () => {
    expect(albumLinkUrl('youtube_music', 'MPREb_abc123')).toBe(
      'https://music.youtube.com/browse/MPREb_abc123',
    )
  })

  it('sends a YouTube Music playlist ID to /playlist', () => {
    expect(albumLinkUrl('youtube_music', 'OLAK5uy_xyz')).toBe(
      'https://music.youtube.com/playlist?list=OLAK5uy_xyz',
    )
  })

  it('passes an already-complete URL through untouched', () => {
    const url = 'https://open.spotify.com/album/3v1nspBDZhlcJGDW6fUJQR?si=abc'
    expect(albumLinkUrl('spotify', url)).toBe(url)
  })

  it('passes Bandcamp and Wikipedia URLs through', () => {
    const bandcamp = 'https://radiohead.bandcamp.com/album/ok-computer'
    const wikipedia = 'https://en.wikipedia.org/wiki/OK_Computer'
    expect(albumLinkUrl('bandcamp', bandcamp)).toBe(bandcamp)
    expect(albumLinkUrl('wikipedia', wikipedia)).toBe(wikipedia)
  })

  it('returns null for URL-native services given a bare value', () => {
    // Nothing sensible to build — these are not ID-based.
    expect(albumLinkUrl('wikipedia', 'OK_Computer')).toBeNull()
    expect(albumLinkUrl('bandcamp', 'ok-computer')).toBeNull()
  })

  it('returns null when there is nothing to link to', () => {
    expect(albumLinkUrl('spotify', null)).toBeNull()
    expect(albumLinkUrl('spotify', undefined)).toBeNull()
    expect(albumLinkUrl('spotify', '')).toBeNull()
    expect(albumLinkUrl('spotify', '   ')).toBeNull()
  })

  it('trims surrounding whitespace', () => {
    expect(albumLinkUrl('spotify', '  abc123  ')).toBe('https://open.spotify.com/album/abc123')
  })
})
