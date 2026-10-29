import { afterEach, describe, expect, it, vi } from 'vitest'
import { isChatSoundEnabled, setChatSoundEnabled, unlockChatSoundOnGesture } from './chatSound'

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

describe('unlockChatSoundOnGesture', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('resumes audio on the first click, then stops listening', async () => {
    const resume = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('AudioContext', class {
      state = 'suspended'
      resume = resume
    })
    const cleanup = unlockChatSoundOnGesture()

    window.dispatchEvent(new Event('pointerdown'))
    await Promise.resolve()
    window.dispatchEvent(new Event('pointerdown'))

    expect(resume).toHaveBeenCalledTimes(1)
    cleanup()
  })
})
