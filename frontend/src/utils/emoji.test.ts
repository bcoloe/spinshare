import { describe, it, expect } from 'vitest'
import { EMOJI, emojiFor, replaceShortcodes, searchEmoji } from './emoji'

describe('emojiFor', () => {
  it('resolves a canonical shortcode', () => {
    expect(emojiFor('fire')).toBe('🔥')
  })

  it('accepts the colons that wrap a shortcode', () => {
    expect(emojiFor(':fire:')).toBe('🔥')
  })

  it('is case insensitive', () => {
    expect(emojiFor('FIRE')).toBe('🔥')
  })

  it('resolves an alias to its canonical emoji', () => {
    expect(emojiFor('+1')).toBe(emojiFor('thumbsup'))
  })

  it('returns null for an unknown shortcode', () => {
    expect(emojiFor('definitely_not_an_emoji')).toBeNull()
  })
})

describe('replaceShortcodes', () => {
  it('substitutes a known shortcode', () => {
    expect(replaceShortcodes('this record is :fire:')).toBe('this record is 🔥')
  })

  it('substitutes several in one message', () => {
    expect(replaceShortcodes(':thumbsup: :notes: :100:')).toBe('👍 🎶 💯')
  })

  it('substitutes adjacent shortcodes with no separator', () => {
    expect(replaceShortcodes(':fire::fire:')).toBe('🔥🔥')
  })

  it('leaves an unknown shortcode exactly as typed', () => {
    expect(replaceShortcodes('ship it :not_a_real_one:')).toBe('ship it :not_a_real_one:')
  })

  it('leaves a timestamp alone', () => {
    // The colons in "12:30:45" look like shortcode delimiters; substitution is
    // gated on the code resolving, which is what keeps them intact.
    expect(replaceShortcodes('starts at 12:30:45')).toBe('starts at 12:30:45')
  })

  it('leaves a url alone', () => {
    const url = 'listen at https://open.spotify.com/album/123'
    expect(replaceShortcodes(url)).toBe(url)
  })

  it('substitutes an alias', () => {
    expect(replaceShortcodes('nice :+1:')).toBe('nice 👍')
  })

  it('returns plain text untouched', () => {
    expect(replaceShortcodes('no emoji here')).toBe('no emoji here')
  })

  it('handles an empty string', () => {
    expect(replaceShortcodes('')).toBe('')
  })
})

describe('searchEmoji', () => {
  it('ranks a prefix match above a substring match', () => {
    const results = searchEmoji('heart', 20)
    expect(results[0].slug).toBe('heart_eyes')
    expect(results.map((e) => e.slug)).toContain('broken_heart')
    expect(results.findIndex((e) => e.slug === 'heart_eyes')).toBeLessThan(
      results.findIndex((e) => e.slug === 'broken_heart'),
    )
  })

  it('respects the limit', () => {
    expect(searchEmoji('a', 4)).toHaveLength(4)
  })

  it('finds an emoji through an alias', () => {
    expect(searchEmoji('vinyl', 5).map((e) => e.char)).toContain('📀')
  })

  it('never returns the same emoji twice', () => {
    // "music" is an alias of :notes:, so a naive search would list it twice.
    const slugs = searchEmoji('mus', 20).map((e) => e.slug)
    expect(new Set(slugs).size).toBe(slugs.length)
  })

  it('returns the head of the list for an empty query', () => {
    expect(searchEmoji('', 3)).toEqual(EMOJI.slice(0, 3))
  })

  it('returns nothing for a query that matches no emoji', () => {
    expect(searchEmoji('zzzzzz', 5)).toEqual([])
  })
})

describe('the emoji table itself', () => {
  it('has no duplicate slugs', () => {
    const slugs = EMOJI.map((e) => e.slug)
    expect(new Set(slugs).size).toBe(slugs.length)
  })

  it('uses only shortcode-safe characters in slugs', () => {
    // A slug outside this charset could be inserted by the picker but would
    // never match the substitution regex on the way back out.
    for (const { slug } of EMOJI) {
      expect(slug).toMatch(/^[a-z0-9_+-]{1,32}$/)
    }
  })
})
