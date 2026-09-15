import { describe, it, expect } from 'vitest'
import { ratingColor, ratingColorHex, ratingColorTint } from './ratingColor'

describe('ratingColor', () => {
  it('returns gray for an absent rating', () => {
    expect(ratingColor(null)).toBe('gray')
  })

  it.each([
    [0, '#9c6634'],
    [0.9, '#9c6634'],
    [1, '#c08552'],
    [2, '#dcb287'],
    [3, 'red.7'],
    [3.9, 'red.7'],
    [4, 'orange.6'],
    [4.9, 'orange.6'],
    [5, 'yellow.6'],
    [6, '#b0d12b'],
    [7, 'green.8'],
    [8, 'blue.6'],
    [9, 'violet.6'],
    [9.9, 'violet.6'],
    [10, 'grape.4'],
  ])('maps %s to %s', (rating, expected) => {
    expect(ratingColor(rating)).toBe(expected)
  })

  it('climbs the scale without repeating a band', () => {
    const bands = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(ratingColor)
    expect(new Set(bands).size).toBe(bands.length)
  })

  it('darkens the brown ramp toward zero', () => {
    const brightness = (hex: string) => parseInt(hex.slice(1), 16)
    expect(brightness(ratingColor(0))).toBeLessThan(brightness(ratingColor(1)))
    expect(brightness(ratingColor(1))).toBeLessThan(brightness(ratingColor(2)))
  })

  it('reserves its top band for a perfect 10 alone', () => {
    const perfect = ratingColor(10)
    for (let rating = 0; rating < 10; rating += 0.1) {
      expect(ratingColor(rating)).not.toBe(perfect)
    }
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
