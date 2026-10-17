/**
 * The formatting subset shared by chat messages and review comments.
 *
 * Content is stored as plain text with two markdown-style markers:
 * `**bold**` and `*italic*`. Underscore emphasis (`_x_`) is deliberately not
 * supported — underscores are common in usernames and ordinary prose
 * (snake_case), and treating them as markup would garble both.
 *
 * Emphasis never spans a line break and must hug its content (`* x *` is not
 * italic), so stray asterisks in prose — "2 * 3 * 4", footnote stars — stay
 * literal. An unclosed marker renders as the text it is.
 */

export type RichNode =
  | { type: 'text'; text: string }
  | { type: 'bold'; children: RichNode[] }
  | { type: 'italic'; children: RichNode[] }

// The closing `**` may not be followed by another '*', so in `***x***` the
// bold closes on the last two stars and the inner `*x*` is left to read as italic.
const BOLD = /\*\*(\S(?:[^\n]*?\S)?)\*\*(?!\*)/
// Italic content is plain characters or whole `**bold**` runs, so italic can
// wrap bold (`*a **b** c*`). It must open and close against a non-space: the
// last unit is a bold run or a non-space character. (No lookbehind — Safari
// before 16.4 cannot compile one.)
const ITALIC = /\*(?![\s*])((?:\*\*[^*\n]+\*\*|[^*\n])*?(?:\*\*[^*\n]+\*\*|[^\s*]))\*/

/** Split text into plain runs and (possibly nested) emphasis spans. */
export function parseRichText(text: string): RichNode[] {
  const nodes: RichNode[] = []
  let rest = text

  while (rest) {
    const bold = BOLD.exec(rest)
    const italic = ITALIC.exec(rest)
    // Whichever span starts first wins; bold on a tie.
    const match =
      bold && (!italic || bold.index <= italic.index) ? { m: bold, type: 'bold' as const } :
      italic ? { m: italic, type: 'italic' as const } :
      null

    if (!match) {
      nodes.push({ type: 'text', text: rest })
      break
    }

    if (match.m.index > 0) nodes.push({ type: 'text', text: rest.slice(0, match.m.index) })
    nodes.push({ type: match.type, children: parseRichText(match.m[1]) })
    rest = rest.slice(match.m.index + match.m[0].length)
  }

  return nodes
}

/** The text with formatting markers removed, for plain-text contexts (previews). */
export function stripFormatting(text: string): string {
  return parseRichText(text).map(nodeText).join('')
}

function nodeText(node: RichNode): string {
  return node.type === 'text' ? node.text : node.children.map(nodeText).join('')
}

export type FormatMarker = '**' | '*'

export interface TextSelection {
  value: string
  start: number
  end: number
}

/** Length of the run of '*' ending at `index` (looking left) or starting there. */
function starRun(value: string, index: number, direction: -1 | 1): number {
  let n = 0
  let i = direction === -1 ? index - 1 : index
  while (i >= 0 && i < value.length && value[i] === '*') {
    n++
    i += direction
  }
  return n
}

/**
 * Toggle a formatting marker around the selection, as the B / I buttons and
 * Ctrl/Cmd+B / Ctrl/Cmd+I do.
 *
 * - Surrounding whitespace is left outside the markers, since emphasis must
 *   hug its content to parse.
 * - Selected text already wrapped in the marker is unwrapped. A run of three
 *   stars is both bold and italic, so star-run parity decides whether a given
 *   marker is present: italic means an odd run, bold a run of two or more.
 * - An empty selection inserts an empty pair with the caret between.
 *
 * Returns the new value with the selection placed on the (un)wrapped text.
 */
export function toggleFormat(sel: TextSelection, marker: FormatMarker): TextSelection {
  const { value } = sel
  let { start, end } = sel
  while (start < end && /\s/.test(value[start])) start++
  while (end > start && /\s/.test(value[end - 1])) end--

  if (start === end) {
    const at = sel.start
    return {
      value: value.slice(0, at) + marker + marker + value.slice(at),
      start: at + marker.length,
      end: at + marker.length,
    }
  }

  const before = starRun(value, start, -1)
  const after = starRun(value, end, 1)
  const has = (run: number) => (marker === '*' ? run % 2 === 1 : run >= 2)

  if (has(before) && has(after)) {
    const len = marker.length
    return {
      value: value.slice(0, start - len) + value.slice(start, end) + value.slice(end + len),
      start: start - len,
      end: end - len,
    }
  }

  return {
    value: value.slice(0, start) + marker + value.slice(start, end) + marker + value.slice(end),
    start: start + marker.length,
    end: end + marker.length,
  }
}
