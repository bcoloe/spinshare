import { describe, it, expect } from 'vitest'
import { DEFAULT_THEME } from '@mantine/core'
import { themeColorHex } from './themeColorHex'

describe('themeColorHex', () => {
  it('resolves a token through Mantine’s own palette', () => {
    expect(themeColorHex('gray.5')).toBe(DEFAULT_THEME.colors.gray[5])
    expect(themeColorHex('violet.6')).toBe(DEFAULT_THEME.colors.violet[6])
  })

  it('passes a raw hex through, so either form can be handed over', () => {
    expect(themeColorHex('#b0d12b')).toBe('#b0d12b')
  })
})
