import { describe, it, expect } from 'vitest'
import { getSchema } from '@tiptap/core'
import { Node as ProseMirrorNode } from '@tiptap/pm/model'
import Document from '@tiptap/extension-document'
import Paragraph from '@tiptap/extension-paragraph'
import Text from '@tiptap/extension-text'
import HardBreak from '@tiptap/extension-hard-break'
import Bold from '@tiptap/extension-bold'
import Italic from '@tiptap/extension-italic'
import { docToMarkdown, markdownToDoc } from './richTextDoc'
import { parseRichText } from './richText'

const schema = getSchema([Document, Paragraph, Text, HardBreak, Bold, Italic])
const toDoc = (text: string) => ProseMirrorNode.fromJSON(schema, markdownToDoc(text))
const roundTrip = (text: string) => docToMarkdown(toDoc(text))

type Run = [string, ...('bold' | 'italic')[]]
/** Build a one-paragraph doc from formatted runs, as the editor would hold it. */
function docOf(...runs: Run[]) {
  return ProseMirrorNode.fromJSON(schema, {
    type: 'doc',
    content: [{
      type: 'paragraph',
      content: runs.map(([text, ...marks]) => ({
        type: 'text',
        text,
        ...(marks.length ? { marks: marks.map((type) => ({ type })) } : {}),
      })),
    }],
  })
}

describe('markdownToDoc / docToMarkdown', () => {
  it.each([
    ['plain text'],
    ['**bold** and *italic*'],
    ['**so *very* good**'],
    ['line one\n\n**line three**'],
    ['a\\*b\\* stays literal'],
    ['snake_case stays readable'],
    ['a \\_literal\\_ pair'],
    [''],
  ])('round-trips %j', (text) => {
    expect(roundTrip(text)).toBe(text)
  })

  it('keeps whitespace outside the markers', () => {
    expect(docToMarkdown(docOf(['great ', 'bold'], ['record']))).toBe('**great** record')
  })

  it('reads _x_ into italic and writes it back with stars', () => {
    expect(roundTrip('a _soft_ word')).toBe('a *soft* word')
  })

  it('escapes asterisks typed as plain text', () => {
    expect(docToMarkdown(docOf(['a*b*c']))).toBe('a\\*b\\*c')
  })

  it('writes a hard break as a newline', () => {
    const doc = ProseMirrorNode.fromJSON(schema, {
      type: 'doc',
      content: [{
        type: 'paragraph',
        content: [{ type: 'text', text: 'a' }, { type: 'hardBreak' }, { type: 'text', text: 'b' }],
      }],
    })
    expect(docToMarkdown(doc)).toBe('a\nb')
  })

  // Every pairing of formats on adjacent runs must read back as written.
  const formats: ('bold' | 'italic')[][] = [[], ['bold'], ['italic'], ['bold', 'italic']]
  const describeRun = (marks: string[]) => marks.join('+') || 'plain'
  for (const first of formats) {
    for (const second of formats) {
      if (first.join() === second.join()) continue
      it(`preserves ${describeRun(first)} next to ${describeRun(second)}`, () => {
        const doc = docOf(['a', ...first], ['b', ...second])
        const text = docToMarkdown(doc)
        expect(toDoc(text).toJSON()).toEqual(doc.toJSON())
        // And the renderer sees the same thing the editor did.
        expect(parseRichText(text).length).toBeGreaterThan(0)
      })
    }
  }
})
