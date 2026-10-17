import type { JSONContent } from '@tiptap/core'
import type { Node as ProseMirrorNode } from '@tiptap/pm/model'
import { escapeFormatting, parseRichText } from './richText'
import type { RichNode } from './richText'

/**
 * Conversion between the stored text format (see `richText.ts`) and the rich
 * editor's document.
 *
 * The editor shows formatting rather than markers, but what is stored never
 * changes: one line of text per paragraph (or hard break), `**bold**` and
 * `*italic*` around formatted runs, and literal asterisks escaped. Everything
 * that renders stored text therefore keeps working unchanged.
 */

type Mark = 'bold' | 'italic'

function nodesToContent(nodes: RichNode[], marks: Mark[] = []): JSONContent[] {
  return nodes.flatMap((node) => {
    if (node.type === 'text') {
      if (!node.text) return []
      return [{
        type: 'text',
        text: node.text,
        ...(marks.length ? { marks: marks.map((type) => ({ type })) } : {}),
      }]
    }
    const next = marks.includes(node.type) ? marks : [...marks, node.type]
    return nodesToContent(node.children, next)
  })
}

/** Stored text → editor document. One paragraph per line. */
export function markdownToDoc(text: string): JSONContent {
  return {
    type: 'doc',
    content: text.split('\n').map((line) => {
      const content = nodesToContent(parseRichText(line))
      return content.length ? { type: 'paragraph', content } : { type: 'paragraph' }
    }),
  }
}

interface Piece {
  text: string
  bold: boolean
  italic: boolean
}

const MARKER: Record<Mark, string> = { bold: '**', italic: '*' }

const has = (piece: Piece, mark: Mark) => piece[mark]

/**
 * Write one line's formatted pieces as text.
 *
 * Emphasis must hug its content to parse, so whitespace at the edge of a
 * formatted run is moved outside its markers. Markers nest like tags: when two
 * open together, the one that runs longer goes outside, and closing a mark
 * closes (then reopens) anything opened inside it. What comes out reads back
 * through `parseRichText` to the same pieces, adjacent runs included.
 */
function writeLine(pieces: Piece[]): string {
  // Split off edge whitespace, then give each whitespace segment only the marks
  // the text on *both* sides of it shares: inside a bold run a space stays
  // bold, but at the run's edge it falls outside the markers.
  const segments = pieces.flatMap((p) => {
    const [, lead, core, trail] = /^(\s*)([\s\S]*?)(\s*)$/.exec(p.text)!
    return [
      { ...p, text: lead, space: true },
      { ...p, text: core, space: false },
      { ...p, text: trail, space: true },
    ].filter((seg) => seg.text)
  })
  const split: Piece[] = segments.map((seg, k) => {
    if (!seg.space) return seg
    const before = segments.slice(0, k).reverse().find((s) => !s.space)
    const after = segments.slice(k + 1).find((s) => !s.space)
    return {
      text: seg.text,
      bold: !!before?.bold && !!after?.bold,
      italic: !!before?.italic && !!after?.italic,
    }
  })

  // How many pieces, from index `k` on, carry `mark` without a break.
  const runLength = (k: number, mark: Mark) => {
    let n = 0
    while (k + n < split.length && has(split[k + n], mark)) n++
    return n
  }

  let out = ''
  const open: Mark[] = []
  split.forEach((piece, k) => {
    // Close from the innermost out down to the first mark this piece drops.
    const firstDropped = open.findIndex((mark) => !has(piece, mark))
    if (firstDropped !== -1) {
      const closing = open.splice(firstDropped)
      for (const mark of [...closing].reverse()) out += MARKER[mark]
    }
    // Open what's missing, longest-running first so it ends up outermost.
    const opening = (['bold', 'italic'] as const)
      .filter((mark) => has(piece, mark) && !open.includes(mark))
      .sort((a, b) => runLength(k, b) - runLength(k, a))
    for (const mark of opening) {
      out += MARKER[mark]
      open.push(mark)
    }
    out += escapeFormatting(piece.text)
  })
  for (const mark of [...open].reverse()) out += MARKER[mark]
  return out
}

/** Editor document → stored text. */
export function docToMarkdown(doc: ProseMirrorNode): string {
  const lines: string[] = []
  doc.forEach((block) => {
    // A hard break (Shift+Enter) is a line break just like a new paragraph.
    let pieces: Piece[] = []
    block.forEach((inline) => {
      if (inline.type.name === 'hardBreak') {
        lines.push(writeLine(pieces))
        pieces = []
        return
      }
      if (!inline.isText) return
      pieces.push({
        text: inline.text ?? '',
        bold: inline.marks.some((m) => m.type.name === 'bold'),
        italic: inline.marks.some((m) => m.type.name === 'italic'),
      })
    })
    lines.push(writeLine(pieces))
  })
  return lines.join('\n')
}
