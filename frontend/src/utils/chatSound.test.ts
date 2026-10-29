import { afterEach, describe, expect, it } from 'vitest'
import { isChatSoundEnabled, setChatSoundEnabled } from './chatSound'

describe('chat sound preference', () => {
  afterEach(() => localStorage.clear())

  it('is on by default', () => {
    expect(isChatSoundEnabled()).toBe(true)
  })

  it('remembers an opt-out and an opt back in', () => {
    setChatSoundEnabled(false)
    expect(isChatSoundEnabled()).toBe(false)
    setChatSoundEnabled(true)
    expect(isChatSoundEnabled()).toBe(true)
  })
})
