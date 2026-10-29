// A short synthesized chime for incoming chat messages.
//
// Synthesized with Web Audio rather than shipped as an audio file: there is no
// asset to host or cache-bust, and a two-partial sine decay is all a "ding"
// needs. The preference is per device (localStorage), not per account — whether
// a laptop should make noise is a property of where it sits, not who is using it.

const PREF_KEY = 'spinshare_chat_sound'
// A burst of messages should ding once, not machine-gun.
const MIN_GAP_MS = 2000

let context: AudioContext | null = null
let lastPlayedAt = 0

export function isChatSoundEnabled(): boolean {
  try {
    return localStorage.getItem(PREF_KEY) !== 'off'
  } catch {
    return true
  }
}

export function setChatSoundEnabled(enabled: boolean): void {
  try {
    if (enabled) localStorage.removeItem(PREF_KEY)
    else localStorage.setItem(PREF_KEY, 'off')
  } catch {}
}

export function playChatDing(): void {
  if (!isChatSoundEnabled()) return
  const now = Date.now()
  if (now - lastPlayedAt < MIN_GAP_MS) return
  lastPlayedAt = now

  try {
    context ??= new AudioContext()
    // Browsers start an AudioContext suspended until the page has had a user
    // gesture. Sound scheduled on a suspended clock would queue and fire all at
    // once on resume, so skip this ding — the unread dot still carries the news.
    if (context.state !== 'running') {
      context.resume().catch(() => {})
      return
    }

    const t = context.currentTime
    const gain = context.createGain()
    gain.connect(context.destination)
    gain.gain.setValueAtTime(0.0001, t)
    gain.gain.exponentialRampToValueAtTime(0.15, t + 0.01)
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.6)

    // Fundamental plus a quieter fifth above gives it a bell-like edge.
    for (const [freq, level] of [[880, 1], [1320, 0.35]] as const) {
      const partial = context.createGain()
      partial.gain.value = level
      partial.connect(gain)
      const osc = context.createOscillator()
      osc.type = 'sine'
      osc.frequency.value = freq
      osc.connect(partial)
      osc.start(t)
      osc.stop(t + 0.6)
    }
  } catch {
    // No Web Audio (old browser, test environment) — sound is a nicety.
  }
}
