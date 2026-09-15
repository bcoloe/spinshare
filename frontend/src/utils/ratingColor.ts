/**
 * Shared rating-color utilities used throughout the app.
 *
 * All exports derive from the single RATING_BANDS table below, so the Mantine
 * tokens, their hex equivalents, and the translucent tints can never drift
 * apart.
 *
 * ratingColor     — Mantine color tokens for `c={}` (Text) and `color={}` (Badge).
 * ratingColorHex  — CSS hex values for inline style properties (background,
 *                   outline, etc.) where Mantine tokens are not accepted.
 * ratingColorTint — translucent band color for row/card backgrounds.
 *
 * Scale (ROYGBIV, low to high):
 *   < 4   red
 *   4–5   orange
 *   5–6   yellow
 *   6–7   light green
 *   7–8   dark green
 *   8–9   blue
 *   ≥ 9   purple
 */

interface RatingBand {
  /** Upper bound of the band, exclusive. */
  max: number
  /** Mantine color token. */
  token: string
  /** Hex equivalent of the token, from the Mantine default palette. */
  hex: string
}

const RATING_BANDS: RatingBand[] = [
  { max: 4, token: 'red.7', hex: '#f03e3e' },
  { max: 5, token: 'orange.6', hex: '#fd7e14' },
  { max: 6, token: 'yellow.6', hex: '#fab005' },
  { max: 7, token: 'lime.6', hex: '#82c91e' },
  { max: 8, token: 'green.8', hex: '#2f9e44' },
  { max: 9, token: 'blue.6', hex: '#228be6' },
  { max: Infinity, token: 'violet.6', hex: '#7950f2' },
]

const TOP_BAND = RATING_BANDS[RATING_BANDS.length - 1]

function bandFor(rating: number): RatingBand {
  return RATING_BANDS.find((band) => rating < band.max) ?? TOP_BAND
}

export function ratingColor(rating: number | null): string {
  if (rating == null) return 'gray'
  return bandFor(rating).token
}

export function ratingColorHex(rating: number): string {
  return bandFor(rating).hex
}

/** Translucent band color, for use as a row or card background. */
export function ratingColorTint(rating: number, percent = 12): string {
  return `color-mix(in srgb, ${bandFor(rating).hex} ${percent}%, transparent)`
}
