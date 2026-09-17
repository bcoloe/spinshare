import { DEFAULT_THEME, parseThemeColor } from '@mantine/core'

/**
 * Shared rating-color utilities used throughout the app.
 *
 * Every rating rendered anywhere — text, badges, slider tracks, chart bars,
 * row tints — takes its color from the RATING_BANDS table below, which is the
 * only place the scale is written down.
 *
 * ratingColor     — the band color for `c={}` (Text) and `color={}` (Badge,
 *                   Slider). Mantine accepts both token and raw-hex forms.
 * ratingColorHex  — the same band resolved to a hex, for SVG fills and other
 *                   places a Mantine token is not understood.
 * ratingColorTint — translucent band color, for row/card backgrounds.
 *
 * All three accept an absent rating and answer with ABSENT_COLOR, so callers
 * never need a fallback of their own.
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
  color: string
}

// Bands carrying a raw hex have no Mantine palette equivalent.
// The bottom three are brown, which Mantine does not ship at all.
// They are tuned to stay legible on the app's dark background: a literal dark
// brown (#3d2312) sits at 1.07:1 against it, effectively invisible.
const RATING_BANDS: RatingBand[] = [
  { max: 1, color: '#9c6634' },
  { max: 2, color: '#c08552' },
  { max: 3, color: '#dcb287' },
  { max: 4, color: 'red.7' },
  { max: 5, color: 'orange.6' },
  { max: 6, color: 'yellow.6' },
  // Mantine's lime shades all sit at hue ~84 (green-leaning); this is pulled
  // to ~72 so the band reads yellow-green, roughly equidistant from the
  // yellow below it and the green above.
  { max: 7, color: '#b0d12b' },
  { max: 8, color: 'green.8' },
  { max: 9, color: 'blue.6' },
  { max: 10, color: 'violet.6' },
  // Reserved for a perfect 10: nothing below 10 reaches this band, because
  // ratings are capped at 10 server-side (ge=0, le=10).
  { max: Infinity, color: 'grape.4' },
]

const TOP_BAND = RATING_BANDS[RATING_BANDS.length - 1]

/** Stands in for an unrated review — deliberately off the ROYGBIV ramp, so a
 *  missing rating can never be read as a low one. */
const ABSENT_COLOR = 'gray'

export function ratingColor(rating: number | null | undefined): string {
  if (rating == null) return ABSENT_COLOR
  return (RATING_BANDS.find((band) => rating < band.max) ?? TOP_BAND).color
}

/**
 * Band color as a hex value.
 *
 * Mantine tokens are resolved through Mantine's own palette rather than
 * transcribed, so the tokens and their hex equivalents cannot drift apart.
 * DEFAULT_THEME is the right source because the app theme (see main.tsx)
 * customizes no palette colors.
 */
export function ratingColorHex(rating: number | null | undefined): string {
  return parseThemeColor({ color: ratingColor(rating), theme: DEFAULT_THEME }).value
}

/** Translucent band color, for use as a row or card background. */
export function ratingColorTint(rating: number | null | undefined, percent = 12): string {
  return `color-mix(in srgb, ${ratingColorHex(rating)} ${percent}%, transparent)`
}
