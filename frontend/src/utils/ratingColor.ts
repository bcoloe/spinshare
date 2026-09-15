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
 * Scale (low to high): a brown ramp for the bottom of the range, then ROYGBIV,
 * capped by a bright purple reserved for a perfect 10.
 *   < 1    dark brown
 *   1–2    medium brown
 *   2–3    light brown
 *   3–4    red
 *   4–5    orange
 *   5–6    yellow
 *   6–7    yellow-green
 *   7–8    dark green
 *   8–9    blue
 *   9–10   purple
 *   10     bright purple
 */

interface RatingBand {
  /** Upper bound of the band, exclusive. */
  max: number
  /** Mantine color token, or a raw hex where the palette has no equivalent. */
  token: string
  /** Hex equivalent of the token, from the Mantine default palette. */
  hex: string
}

// Bands carrying a raw hex have no Mantine palette equivalent.
// The bottom three are brown, which Mantine does not ship at all.
// They are tuned to stay legible on the app's dark background: a literal dark
// brown (#3d2312) sits at 1.07:1 against it, effectively invisible.
const RATING_BANDS: RatingBand[] = [
  { max: 1, token: '#9c6634', hex: '#9c6634' },
  { max: 2, token: '#c08552', hex: '#c08552' },
  { max: 3, token: '#dcb287', hex: '#dcb287' },
  { max: 4, token: 'red.7', hex: '#f03e3e' },
  { max: 5, token: 'orange.6', hex: '#fd7e14' },
  { max: 6, token: 'yellow.6', hex: '#fab005' },
  // Mantine's lime shades all sit at hue ~84 (green-leaning); this is pulled
  // to ~72 so the band reads yellow-green, roughly equidistant from the
  // yellow below it and the green above.
  { max: 7, token: '#b0d12b', hex: '#b0d12b' },
  { max: 8, token: 'green.8', hex: '#2f9e44' },
  { max: 9, token: 'blue.6', hex: '#228be6' },
  { max: 10, token: 'violet.6', hex: '#7950f2' },
  // Reserved for a perfect 10: nothing below 10 reaches this band, because
  // ratings are capped at 10 server-side (ge=0, le=10).
  { max: Infinity, token: 'grape.4', hex: '#da77f2' },
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
