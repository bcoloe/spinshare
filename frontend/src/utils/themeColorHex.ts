import { DEFAULT_THEME, parseThemeColor } from '@mantine/core'

/**
 * A Mantine color token — "gray.5", "violet.6" — resolved to its hex value,
 * for SVG fills and anywhere else a token means nothing.
 *
 * Tokens are resolved through Mantine's own palette rather than transcribed, so
 * a token and its hex equivalent cannot drift apart. DEFAULT_THEME is the right
 * source because the app theme (see main.tsx) customizes no palette colors —
 * the one assumption here, which is why it is written down once.
 *
 * A raw hex passes straight through, so callers holding either form can hand it
 * over without checking which they have.
 */
export function themeColorHex(color: string): string {
  return parseThemeColor({ color, theme: DEFAULT_THEME }).value
}
