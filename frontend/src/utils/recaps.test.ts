import { describe, it, expect } from 'vitest'
import { isRecapEligible } from './recaps'
import type { GroupSettings } from '../types/group'

function group(overrides: { is_global?: boolean; is_bot_group?: boolean; dealer_mode?: boolean } = {}) {
  return {
    is_global: overrides.is_global ?? false,
    is_bot_group: overrides.is_bot_group ?? false,
    settings: { dealer_mode: overrides.dealer_mode ?? false } as GroupSettings,
  }
}

describe('isRecapEligible', () => {
  it('is true for a regular member group', () => {
    expect(isRecapEligible(group())).toBe(true)
  })

  it('is true when settings are missing', () => {
    expect(isRecapEligible({ is_global: false, is_bot_group: false, settings: null })).toBe(true)
  })

  it.each([
    ['global', { is_global: true }],
    ['bot', { is_bot_group: true }],
    ['dealer-mode', { dealer_mode: true }],
  ])('is false for a %s group', (_label, overrides) => {
    expect(isRecapEligible(group(overrides))).toBe(false)
  })
})
