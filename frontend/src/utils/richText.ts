/**
 * The formatting subset shared by chat messages and review comments.
 *
 * Content is stored as plain text with markdown-style markers: `**bold**`,
 * `*italic*` and `_italic_`. Only a single underscore means anything — `__x__`
 * stays literal.
 *
 * Emphasis follows CommonMark's rules: it never spans a line break and must hug
 * its content (`* x *` is not italic), so stray asterisks in prose — "2 * 3 * 4",
 * footnote stars — stay literal. Underscores additionally never open or close
 * inside a word, so `snake_case` and `@foo_bar_baz` are safe. An unclosed
 * marker renders as the text it is.
 *
 * A backslash escapes the next `*`, `_` or `\\`. The editor writes these for
 * markers the user typed as plain text, so they never turn into formatting when
 * the stored text is read back.
 */

export type RichNode =
  | { type: 'text'; text: string }
  | { type: 'bold'; children: RichNode[] }
  | { type: 'italic'; children: RichNode[] }

// Escaped characters are swapped for private-use placeholders while parsing, so
// the emphasis algorithm never sees them, then restored in the output text.
const ESCAPES: Record<string, string> = { '*': '\uE000', '\\': '\uE001', _: '\uE002' }
const UNESCAPES: Record<string, string> = Object.fromEntries(
  Object.entries(ESCAPES).map(([ch, placeholder]) => [placeholder, ch]),
)

function hideEscapes(text: string): string {
  return text.replace(/\\([\\*_])/g, (_, ch: string) => ESCAPES[ch])
}

function restoreEscapes(text: string): string {
  return text.replace(/[\uE000-\uE002]/g, (ch) => UNESCAPES[ch])
}

const isWordChar = (ch: string | undefined) => !!ch && /[\p{L}\p{N}]/u.test(ch)

/**
 * Escape text so it reads back literally. `*` and `\\` always gain a
 * backslash; `_` only where it could act as a marker — inside a word, as in
 * `snake_case`, it never can, so it is left readable.
 */
export function escapeFormatting(text: string): string {
  return text.replace(/[\\*_]/g, (ch, i: number) =>
    ch === '_' && isWordChar(text[i - 1]) && isWordChar(text[i + 1]) ? ch : `\\${ch}`,
  )
}

/** Split text into plain runs and (possibly nested) emphasis spans. */
export function parseRichText(text: string): RichNode[] {
  const lines = text.split('\n').map((line) => parseLine(hideEscapes(line)))
  const newline: RichNode = { type: 'text', text: '\n' }
  return mergeText(lines.flatMap((nodes, i) => (i === 0 ? nodes : [newline, ...nodes])))
}

// ---- CommonMark emphasis, for '*' and single '_' ---------------------------
//
// This follows the CommonMark spec's delimiter-run algorithm (§6.2 and the
// "process emphasis" procedure) rather than ad-hoc regexes, because the editor
// writes adjacent and nested runs — `**a***b*`, `***a**b*`, `***a***b` — that
// no pair of regexes reads back correctly in every combination.

type Delim = {
  kind: 'delim'
  char: '*' | '_'
  count: number
  /** Run length before any stars were used — the "rule of 3" needs it. */
  original: number
  canOpen: boolean
  canClose: boolean
}
type Item = { kind: 'text'; text: string } | { kind: 'node'; node: RichNode } | Delim

const isWhitespace = (ch: string) => /\s/.test(ch)
// Escaped markers count as punctuation: they are a literal '*', '_' or '\\'.
const isPunctuation = (ch: string) => ch in UNESCAPES || /[\p{P}\p{S}]/u.test(ch)

function tokenize(line: string): Item[] {
  const items: Item[] = []
  const runs = /\*+|_+/g
  let last = 0
  for (let m = runs.exec(line); m; m = runs.exec(line)) {
    if (m.index > last) items.push({ kind: 'text', text: line.slice(last, m.index) })
    // Line edges count as whitespace.
    const before = m.index > 0 ? line[m.index - 1] : ' '
    const after = m.index + m[0].length < line.length ? line[m.index + m[0].length] : ' '
    const leftFlanking =
      !isWhitespace(after) &&
      (!isPunctuation(after) || isWhitespace(before) || isPunctuation(before))
    const rightFlanking =
      !isWhitespace(before) &&
      (!isPunctuation(before) || isWhitespace(after) || isPunctuation(after))

    const char = m[0][0] as '*' | '_'
    if (char === '_' && m[0].length > 1) {
      // Only `_x_` is italic; a longer underscore run is just text.
      items.push({ kind: 'text', text: m[0] })
    } else {
      items.push({
        kind: 'delim',
        char,
        count: m[0].length,
        original: m[0].length,
        // CommonMark: an underscore can't open or close inside a word.
        canOpen: char === '*' ? leftFlanking : leftFlanking && (!rightFlanking || isPunctuation(before)),
        canClose: char === '*' ? rightFlanking : rightFlanking && (!leftFlanking || isPunctuation(after)),
      })
    }
    last = m.index + m[0].length
  }
  if (last < line.length) items.push({ kind: 'text', text: line.slice(last) })
  return items
}

/** CommonMark's "rule of 3": `*foo**bar*` must not pair the `*` with the `**`. */
function violatesRuleOfThree(opener: Delim, closer: Delim): boolean {
  if (!opener.canClose && !closer.canOpen) return false
  return (
    (opener.original + closer.original) % 3 === 0 &&
    !(opener.original % 3 === 0 && closer.original % 3 === 0)
  )
}

function parseLine(line: string): RichNode[] {
  const items = tokenize(line)

  let i = 0
  while (i < items.length) {
    const closer = items[i]
    if (closer.kind !== 'delim' || !closer.canClose || closer.count === 0) {
      i++
      continue
    }

    let j = i - 1
    for (; j >= 0; j--) {
      const candidate = items[j]
      if (
        candidate.kind === 'delim' &&
        candidate.char === closer.char &&
        candidate.canOpen &&
        candidate.count > 0 &&
        !violatesRuleOfThree(candidate, closer)
      ) {
        break
      }
    }
    if (j < 0) {
      i++
      continue
    }

    const opener = items[j] as Delim
    const used = opener.count >= 2 && closer.count >= 2 ? 2 : 1
    opener.count -= used
    closer.count -= used

    const node: RichNode = {
      type: used === 2 ? 'bold' : 'italic',
      children: toNodes(items.slice(j + 1, i)),
    }
    items.splice(j + 1, i - j - 1, { kind: 'node', node })
    i = j + 2 // the closer, now just after the new node

    if (opener.count === 0) {
      items.splice(j, 1)
      i--
    }
    if (closer.count === 0) items.splice(i, 1)
    // Otherwise the closer has stars left: try it again against earlier openers.
  }

  return toNodes(items)
}

/** Unused delimiter stars become literal text. */
function toNodes(items: Item[]): RichNode[] {
  return mergeText(
    items.flatMap((item): RichNode[] => {
      if (item.kind === 'node') return [item.node]
      const text = item.kind === 'text' ? item.text : item.char.repeat(item.count)
      return text ? [{ type: 'text', text: restoreEscapes(text) }] : []
    }),
  )
}

function mergeText(nodes: RichNode[]): RichNode[] {
  const merged: RichNode[] = []
  for (const node of nodes) {
    const prev = merged[merged.length - 1]
    if (node.type === 'text' && prev?.type === 'text') {
      merged[merged.length - 1] = { type: 'text', text: prev.text + node.text }
    } else {
      merged.push(node)
    }
  }
  return merged
}

/** The text with formatting markers removed, for plain-text contexts (previews). */
export function stripFormatting(text: string): string {
  return parseRichText(text).map(nodeText).join('')
}

function nodeText(node: RichNode): string {
  return node.type === 'text' ? node.text : node.children.map(nodeText).join('')
}
