import { describe, it, expect } from 'vitest'
import { parseRichText, stripFormatting, toggleFormat } from './richText'

describe('parseRichText', () => {
  it('returns a single text node for plain text', () => {
    expect(parseRichText('just words')).toEqual([{ type: 'text', text: 'just words' }])
  })

  it('parses bold and italic spans', () => {
    expect(parseRichText('a **b** *c* d')).toEqual([
      { type: 'text', text: 'a ' },
      { type: 'bold', children: [{ type: 'text', text: 'b' }] },
      { type: 'text', text: ' ' },
      { type: 'italic', children: [{ type: 'text', text: 'c' }] },
      { type: 'text', text: ' d' },
    ])
  })

  it('nests italic inside bold', () => {
    expect(parseRichText('**so *very* good**')).toEqual([
      {
        type: 'bold',
        children: [
          { type: 'text', text: 'so ' },
          { type: 'italic', children: [{ type: 'text', text: 'very' }] },
          { type: 'text', text: ' good' },
        ],
      },
    ])
  })

  it('reads a triple-star run as bold italic', () => {
    expect(parseRichText('***wow***')).toEqual([
      { type: 'bold', children: [{ type: 'italic', children: [{ type: 'text', text: 'wow' }] }] },
    ])
  })

  it.each([
    ['2 * 3 * 4'],
    ['* not italic *'],
    ['unclosed *marker'],
    ['**unclosed bold'],
    ['across *lines\nnope*'],
    ['snake_case _stays_ literal'],
  ])('leaves %j literal', (text) => {
    expect(parseRichText(text)).toEqual([{ type: 'text', text }])
  })
})

describe('stripFormatting', () => {
  it('removes markers and keeps the text', () => {
    expect(stripFormatting('**Great** record, *loved* it')).toBe('Great record, loved it')
  })

  it('leaves unparsed asterisks alone', () => {
    expect(stripFormatting('2 * 3')).toBe('2 * 3')
  })
})

describe('toggleFormat', () => {
  it('wraps the selection and keeps it selected', () => {
    expect(toggleFormat({ value: 'a good one', start: 2, end: 6 }, '**')).toEqual({
      value: 'a **good** one',
      start: 4,
      end: 8,
    })
  })

  it('keeps surrounding whitespace outside the markers', () => {
    expect(toggleFormat({ value: 'a good one', start: 1, end: 7 }, '*').value).toBe('a *good* one')
  })

  it('inserts an empty pair at an empty selection', () => {
    expect(toggleFormat({ value: 'ab', start: 1, end: 1 }, '**')).toEqual({
      value: 'a****b',
      start: 3,
      end: 3,
    })
  })

  it('unwraps an already-wrapped selection', () => {
    expect(toggleFormat({ value: 'a *good* one', start: 3, end: 7 }, '*')).toEqual({
      value: 'a good one',
      start: 2,
      end: 6,
    })
  })

  it('italicises bold text rather than unwrapping it', () => {
    expect(toggleFormat({ value: '**good**', start: 2, end: 6 }, '*').value).toBe('***good***')
  })

  it('removes only the italic from bold italic text', () => {
    expect(toggleFormat({ value: '***good***', start: 3, end: 7 }, '*').value).toBe('**good**')
  })

  it('removes only the bold from bold italic text', () => {
    expect(toggleFormat({ value: '***good***', start: 3, end: 7 }, '**').value).toBe('*good*')
  })
})
