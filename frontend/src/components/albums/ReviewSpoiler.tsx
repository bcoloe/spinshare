import type { CSSProperties, ReactNode } from 'react'
import { Box, Button, Tooltip, VisuallyHidden } from '@mantine/core'
import { IconEye, IconEyeOff } from '@tabler/icons-react'

/**
 * Spoiler guard for other people's opinions of an album.
 *
 * A viewer who has not published their own review gets the global score blurred
 * and its histogram withheld outright, and every reviewer's name, number and
 * notes blurred behind a second guard, so neither the collective verdict nor
 * whose verdict it is can anchor their own.
 *
 * What a guard does to a value depends on where that value keeps its meaning. A
 * numeral keeps it in the glyph, so a blur destroys it — though the blur alone
 * is not enough, since color would still carry the band (see
 * {@link SPOILER_COLOR}). A chart keeps it in the shape, which no blur or
 * recolor touches, so the histogram is not rendered at all; AlbumRatingSummary
 * stands a placeholder in its place.
 *
 * The two guards lift independently: the aggregate is a far smaller spoiler
 * than reading what someone wrote, and plenty of people will want one without
 * the other.
 *
 * The guard is a nudge, not a secret — a click lifts it, and the counts stay in
 * the clear so the page still says how many people got there first.
 */

const BLURRED: CSSProperties = {
  // Mounted but inert: no tooltip, no caret, no drag-select to read through.
  pointerEvents: 'none',
  userSelect: 'none',
}

/**
 * The color a guarded rating is painted in while its guard is up.
 *
 * Blurring the digits is not enough on its own, because the rating scale is a
 * ROYGBIV ramp (see utils/ratingColor) and color survives a blur intact: a
 * purple smear is a 9 and a red one is a 3, however unreadable the numeral.
 * Guarded values drop to a flat neutral — deliberately off the ramp, so there
 * is no band left to read — and take their color back when the guard lifts.
 *
 * Only values whose meaning lives in the glyph are treated this way. A chart,
 * whose meaning is its shape, is not rescued by recoloring and comes out of the
 * page instead (see AlbumRatingSummary).
 */
export const SPOILER_COLOR = 'gray.5'

/**
 * The line each guarded section shows beside its toggle.
 *
 * Shared so the two cannot be reworded apart — this module owns the rest of the
 * guard's wording, including the toggle's own labels and tooltip.
 */
export const SPOILER_HINT = 'Hidden until you post your review.'

interface SpoilerBlurProps {
  /** Whether to obscure the content. */
  hidden: boolean
  /**
   * Blur radius in px. Scale it with what it covers — a 40px numeral needs far
   * more smearing than a line of 12px text before it stops being readable.
   */
  strength?: number
  /** Announced in place of the content while it is hidden. */
  label?: string
  children: ReactNode
}

/**
 * Blurs its children while `hidden`, keeping them mounted so the toggle is
 * instant. The wrapper exists in both states, so lifting the guard does not
 * reflow the page around it.
 */
export function SpoilerBlur({ hidden, strength = 6, label, children }: SpoilerBlurProps) {
  return (
    <>
      {hidden && label && <VisuallyHidden>{label}</VisuallyHidden>}
      <Box
        aria-hidden={hidden || undefined}
        style={hidden ? { ...BLURRED, filter: `blur(${strength}px)` } : undefined}
      >
        {children}
      </Box>
    </>
  )
}

interface SpoilerToggleProps {
  hidden: boolean
  onToggle: () => void
  /**
   * What this toggle covers, named for the button and the tooltip — "global
   * score", "reviews". Phrased as a gerund object so singular and plural
   * subjects both read correctly.
   */
  subject: string
}

/**
 * Reveals or re-hides one of the guards set by {@link SpoilerBlur}.
 *
 * Styled to carry weight while its guard is up, since it is the only way past
 * it, then to step back into the furniture once it has been used.
 */
export function SpoilerToggle({ hidden, onToggle, subject }: SpoilerToggleProps) {
  return (
    <Tooltip
      label={hidden
        ? `You haven't reviewed this album yet — seeing the ${subject} first can sway your own rating.`
        : `Put the ${subject} back behind the blur.`}
      multiline
      w={280}
      withArrow
    >
      <Button
        size="xs"
        variant={hidden ? 'light' : 'subtle'}
        color={hidden ? undefined : 'gray'}
        leftSection={hidden ? <IconEye size={15} /> : <IconEyeOff size={15} />}
        onClick={onToggle}
      >
        {hidden ? `Show ${subject}` : `Hide ${subject}`}
      </Button>
    </Tooltip>
  )
}
