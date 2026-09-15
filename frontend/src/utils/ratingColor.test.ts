import { describe, it, expect } from 'vitest'
import { ratingColor, ratingColorHex, ratingColorTint } from './ratingColor'

describe('ratingColor', () => {
  it('returns gray for an absent rating', () => {
    expect(ratingColor(null)).toBe('gray')
  })

  it.each([
    [1, 'red.7'],
    [3.9, 'red.7'],
    [4, 'orange.6'],
    [4.9, 'orange.6'],
    [5, 'yellow.6'],
    [6, 'lime.6'],
    [7, 'green.8'],
    [8, 'blue.6'],
    [9, 'violet.6'],
    [10, 'violet.6'],
  ])('maps %s to %s', (rating, expected) => {
    expect(ratingColor(rating)).toBe(expected)
  })

  it('climbs the ROYGBIV scale without repeating a band', () => {
    const bands = [1, 4, 5, 6, 7, 8, 9].map(ratingColor)
    expect(new Set(bands).size).toBe(bands.length)
  })
})

describe('ratingColorHex', () => {
  it('returns a hex value rather than a Mantine token', () => {
    expect(ratingColorHex(6.5)).toMatch(/^#[0-9a-f]{6}$/)
  })

  it('changes bands at the same thresholds as ratingColor', () => {
    for (let rating = 0; rating <= 10; rating += 0.5) {
      const sameBand = ratingColor(rating) === ratingColor(rating + 0.5)
      expect(ratingColorHex(rating) === ratingColorHex(rating + 0.5)).toBe(sameBand)
    }
  })
})

describe('ratingColorTint', () => {
  it('tints the band hex at the default weight', () => {
    expect(ratingColorTint(9)).toBe(`color-mix(in srgb, ${ratingColorHex(9)} 12%, transparent)`)
  })

  it('accepts an explicit weight', () => {
    expect(ratingColorTint(9, 30)).toContain('30%')
  })
})
