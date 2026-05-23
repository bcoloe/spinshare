/**
 * Shared rating-color utilities used throughout the app.
 *
 * ratingColor   — returns Mantine color tokens for use in `c={}` (Text) and
 *                 `color={}` (Badge) props.
 * ratingColorHex — returns CSS hex values for use in inline style properties
 *                  (background, outline, etc.) where Mantine tokens are not
 *                  accepted.
 *
 * Scale:
 *   < 3   red
 *   3–5   brown
 *   5–7   orange
 *   7–8   blue
 *   8–9   lime (dark)
 *   ≥ 9   green
 */

export function ratingColor(rating: number | null): string {
  if (rating == null) return 'gray'
  if (rating < 3) return 'red.7'
  if (rating < 5) return '#6b4226'
  if (rating < 7) return 'orange.5'
  if (rating < 8) return 'blue.6'
  if (rating < 9) return 'lime.7'
  return 'green.7'
}

// Hex equivalents of the Mantine tokens above, for use in CSS style objects.
// yellow.7 = #f59f00, lime.7 = #74b816
export function ratingColorHex(rating: number): string {
  if (rating < 3) return '#fa5252'  // red.6
  if (rating < 5) return '#6b4226'
  if (rating < 7) return '#fd7e14'  // orange.6
  if (rating < 8) return '#228be6'  // blue.6
  if (rating < 9) return '#74b816'  // lime.7
  return '#40c057'                  // green.6
}
