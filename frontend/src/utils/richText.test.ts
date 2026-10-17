import { describe, it, expect } from 'vitest'
import { escapeFormatting, parseRichText, stripFormatting } from './richText'
import type { RichNode } from './richText'

const t = (text: string): RichNode => ({ type: 'text', text })
const b = (...children: RichNode[]): RichNode => ({ type: 'bold', children })
const i = (...children: RichNode[]): RichNode => ({ type: 'italic', children })

describe('parseRichText', () => {
  it('returns a single text node for plain text', () => {
    expect(parseRichText('just words')).toEqual([t('just words')])
  })

  it('parses bold and italic spans', () => {
    expect(parseRichText('a **b** *c* d')).toEqual([t('a '), b(t('b')), t(' '), i(t('c')), t(' d')])
  })

  it('nests italic inside bold', () => {
    expect(parseRichText('**so *very* good**')).toEqual([b(t('so '), i(t('very')), t(' good'))])
  })

  it('lets italic wrap bold', () => {
    expect(parseRichText('*a **b** c*')).toEqual([i(t('a '), b(t('b')), t(' c'))])
  })

  it('reads a triple-star run as bold italic', () => {
    expect(parseRichText('***wow***')).toEqual([i(b(t('wow')))])
  })

  // Adjacent runs with no separator — what the editor writes when formatting
  // changes mid-word. Each must read back as exactly what was written.
  it.each([
    ['**a***b*', [b(t('a')), i(t('b'))]],
    ['*a***b**', [i(t('a')), b(t('b'))]],
    ['***a*b**', [b(i(t('a')), t('b'))]],
    ['**a*b***', [b(t('a'), i(t('b')))]],
    ['***a**b*', [i(b(t('a')), t('b'))]],
    ['*a**b***', [i(t('a'), b(t('b')))]],
    ['***a***b', [i(b(t('a'))), t('b')]],
  ])('reads %j unambiguously', (text, expected) => {
    expect(parseRichText(text)).toEqual(expected)
  })

  it.each([
    ['2 * 3 * 4'],
    ['* not italic *'],
    ['unclosed *marker'],
    ['**unclosed bold'],
    ['snake_case and @foo_bar_baz'],
    ['__double__ underscores'],
  ])('leaves %j literal', (text) => {
    expect(parseRichText(text)).toEqual([t(text)])
  })

  it('reads single underscores as italic', () => {
    expect(parseRichText('a _soft_ word')).toEqual([t('a '), i(t('soft')), t(' word')])
  })

  it('never pairs an underscore with a star', () => {
    expect(parseRichText('_a*')).toEqual([t('_a*')])
  })

  it('nests bold inside underscore italic', () => {
    expect(parseRichText('_so **very** good_')).toEqual([i(t('so '), b(t('very')), t(' good'))])
  })

  it('never lets emphasis cross a line break', () => {
    expect(parseRichText('across *lines\nnope*')).toEqual([t('across *lines\nnope*')])
  })

  it('formats each line independently', () => {
    expect(parseRichText('**a**\n*b*')).toEqual([b(t('a')), t('\n'), i(t('b'))])
  })

  it('treats escaped stars and backslashes as literal text', () => {
    expect(parseRichText('a\\*b\\* c\\\\')).toEqual([t('a*b* c\\')])
  })

  it('formats around escaped stars', () => {
    expect(parseRichText('**5\\*3**')).toEqual([b(t('5*3'))])
  })
})

describe('escapeFormatting', () => {
  it('escapes markers so they read back literally', () => {
    const raw = 'a*b*c \\ **d** _e_'
    expect(parseRichText(escapeFormatting(raw))).toEqual([t(raw)])
  })

  it('leaves underscores inside words unescaped', () => {
    expect(escapeFormatting('snake_case _x_')).toBe('snake_case \\_x\\_')
  })
})

describe('stripFormatting', () => {
  it('removes markers and keeps the text', () => {
    expect(stripFormatting('**Great** record, *loved* it')).toBe('Great record, loved it')
  })

  it('leaves unparsed asterisks alone', () => {
    expect(stripFormatting('2 * 3')).toBe('2 * 3')
  })

  it('unescapes escaped stars', () => {
    expect(stripFormatting('5\\*3')).toBe('5*3')
  })
})
