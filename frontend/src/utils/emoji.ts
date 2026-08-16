/**
 * Emoji for chat — Slack-style `:shortcode:` typing, and the picker's browse list.
 *
 * Deliberately a hand-kept list rather than a dependency. The full emoji
 * datasets (emoji-mart, node-emoji) ship 100–500KB of data and a supply-chain
 * surface to support thousands of codes, when a chat room realistically uses a
 * few dozen. This list is a few KB, needs no maintenance to keep working, and
 * is trivial to extend — add a row and it is immediately searchable, insertable
 * and substitutable.
 *
 * Shortcodes are resolved in the composer *before* the message is sent, so what
 * lands in the database is plain Unicode. That keeps every downstream consumer
 * — the message list, the socket payload, notification text, anyone reading the
 * table — free of shortcode knowledge, and means a message reads the same
 * everywhere including on clients that predate this feature.
 */

export interface EmojiEntry {
  slug: string
  char: string
}

export interface EmojiGroup {
  name: string
  emoji: readonly EmojiEntry[]
}

/**
 * Canonical entries, grouped for the picker and ordered within each group by
 * roughly how often a chat room reaches for them.
 *
 * Grouping lives here rather than in the picker so the browse order and the
 * search order come from one list — a picker that ordered them separately
 * would drift the moment an entry was added.
 *
 * Names follow Slack/GitHub conventions so muscle memory carries over.
 */
export const EMOJI_GROUPS: readonly EmojiGroup[] = [
  {
    name: 'Smileys',
    emoji: [
      { slug: 'smile', char: '😄' },
      { slug: 'smiley', char: '😃' },
      { slug: 'grin', char: '😁' },
      { slug: 'laughing', char: '😆' },
      { slug: 'joy', char: '😂' },
      { slug: 'rofl', char: '🤣' },
      { slug: 'sweat_smile', char: '😅' },
      { slug: 'slightly_smiling_face', char: '🙂' },
      { slug: 'upside_down_face', char: '🙃' },
      { slug: 'wink', char: '😉' },
      { slug: 'blush', char: '😊' },
      { slug: 'innocent', char: '😇' },
      { slug: 'heart_eyes', char: '😍' },
      { slug: 'star_struck', char: '🤩' },
      { slug: 'kissing_heart', char: '😘' },
      { slug: 'yum', char: '😋' },
      { slug: 'stuck_out_tongue', char: '😛' },
      { slug: 'stuck_out_tongue_winking_eye', char: '😜' },
      { slug: 'zany_face', char: '🤪' },
      { slug: 'sunglasses', char: '😎' },
      { slug: 'nerd_face', char: '🤓' },
      { slug: 'thinking_face', char: '🤔' },
      { slug: 'face_with_raised_eyebrow', char: '🤨' },
      { slug: 'neutral_face', char: '😐' },
      { slug: 'expressionless', char: '😑' },
      { slug: 'no_mouth', char: '😶' },
      { slug: 'smirk', char: '😏' },
      { slug: 'unamused', char: '😒' },
      { slug: 'roll_eyes', char: '🙄' },
      { slug: 'grimacing', char: '😬' },
      { slug: 'lying_face', char: '🤥' },
      { slug: 'relieved', char: '😌' },
      { slug: 'pensive', char: '😔' },
      { slug: 'sleepy', char: '😪' },
      { slug: 'sleeping', char: '😴' },
      { slug: 'mask', char: '😷' },
      { slug: 'nauseated_face', char: '🤢' },
      { slug: 'exploding_head', char: '🤯' },
      { slug: 'cowboy_hat_face', char: '🤠' },
      { slug: 'partying_face', char: '🥳' },
      { slug: 'melting_face', char: '🫠' },
      { slug: 'confused', char: '😕' },
      { slug: 'worried', char: '😟' },
      { slug: 'frowning_face', char: '🙁' },
      { slug: 'astonished', char: '😲' },
      { slug: 'flushed', char: '😳' },
      { slug: 'pleading_face', char: '🥺' },
      { slug: 'cry', char: '😢' },
      { slug: 'sob', char: '😭' },
      { slug: 'scream', char: '😱' },
      { slug: 'confounded', char: '😖' },
      { slug: 'weary', char: '😩' },
      { slug: 'tired_face', char: '😫' },
      { slug: 'triumph', char: '😤' },
      { slug: 'rage', char: '😡' },
      { slug: 'angry', char: '😠' },
      { slug: 'skull', char: '💀' },
      { slug: 'poop', char: '💩' },
      { slug: 'clown_face', char: '🤡' },
      { slug: 'ghost', char: '👻' },
      { slug: 'alien', char: '👽' },
      { slug: 'robot', char: '🤖' },
      { slug: 'see_no_evil', char: '🙈' },
      { slug: 'hear_no_evil', char: '🙉' },
      { slug: 'speak_no_evil', char: '🙊' },
    ],
  },
  {
    name: 'People',
    emoji: [
      { slug: 'thumbsup', char: '👍' },
      { slug: 'thumbsdown', char: '👎' },
      { slug: 'ok_hand', char: '👌' },
      { slug: 'clap', char: '👏' },
      { slug: 'raised_hands', char: '🙌' },
      { slug: 'pray', char: '🙏' },
      { slug: 'wave', char: '👋' },
      { slug: 'point_up', char: '☝️' },
      { slug: 'point_right', char: '👉' },
      { slug: 'point_left', char: '👈' },
      { slug: 'muscle', char: '💪' },
      { slug: 'fist', char: '✊' },
      { slug: 'punch', char: '👊' },
      { slug: 'v', char: '✌️' },
      { slug: 'crossed_fingers', char: '🤞' },
      { slug: 'metal', char: '🤘' },
      { slug: 'call_me_hand', char: '🤙' },
      { slug: 'handshake', char: '🤝' },
      { slug: 'writing_hand', char: '✍️' },
      { slug: 'shrug', char: '🤷' },
      { slug: 'facepalm', char: '🤦' },
      { slug: 'dancer', char: '💃' },
      { slug: 'man_dancing', char: '🕺' },
      { slug: 'eyes', char: '👀' },
      { slug: 'brain', char: '🧠' },
      { slug: 'ear', char: '👂' },
    ],
  },
  {
    name: 'Hearts',
    emoji: [
      { slug: 'heart', char: '❤️' },
      { slug: 'orange_heart', char: '🧡' },
      { slug: 'yellow_heart', char: '💛' },
      { slug: 'green_heart', char: '💚' },
      { slug: 'blue_heart', char: '💙' },
      { slug: 'purple_heart', char: '💜' },
      { slug: 'black_heart', char: '🖤' },
      { slug: 'broken_heart', char: '💔' },
      { slug: 'sparkling_heart', char: '💖' },
      { slug: 'heartpulse', char: '💗' },
    ],
  },
  {
    name: 'Music',
    emoji: [
      { slug: 'notes', char: '🎶' },
      { slug: 'musical_note', char: '🎵' },
      { slug: 'headphones', char: '🎧' },
      { slug: 'microphone', char: '🎤' },
      { slug: 'guitar', char: '🎸' },
      { slug: 'violin', char: '🎻' },
      { slug: 'trumpet', char: '🎺' },
      { slug: 'saxophone', char: '🎷' },
      { slug: 'drum', char: '🥁' },
      { slug: 'musical_keyboard', char: '🎹' },
      { slug: 'accordion', char: '🪗' },
      { slug: 'banjo', char: '🪕' },
      { slug: 'cd', char: '💿' },
      { slug: 'dvd', char: '📀' },
      { slug: 'radio', char: '📻' },
      { slug: 'speaker', char: '🔊' },
      { slug: 'mute', char: '🔇' },
      { slug: 'record_button', char: '⏺️' },
      { slug: 'play_button', char: '▶️' },
      { slug: 'pause_button', char: '⏸️' },
      { slug: 'level_slider', char: '🎚️' },
      { slug: 'control_knobs', char: '🎛️' },
      { slug: 'studio_microphone', char: '🎙️' },
    ],
  },
  {
    name: 'Symbols',
    emoji: [
      { slug: 'fire', char: '🔥' },
      { slug: '100', char: '💯' },
      { slug: 'sparkles', char: '✨' },
      { slug: 'star', char: '⭐' },
      { slug: 'star2', char: '🌟' },
      { slug: 'boom', char: '💥' },
      { slug: 'zap', char: '⚡' },
      { slug: 'tada', char: '🎉' },
      { slug: 'confetti_ball', char: '🎊' },
      { slug: 'trophy', char: '🏆' },
      { slug: 'medal', char: '🏅' },
      { slug: 'crown', char: '👑' },
      { slug: 'gem', char: '💎' },
      { slug: 'rocket', char: '🚀' },
      { slug: 'white_check_mark', char: '✅' },
      { slug: 'x', char: '❌' },
      { slug: 'warning', char: '⚠️' },
      { slug: 'question', char: '❓' },
      { slug: 'exclamation', char: '❗' },
      { slug: 'bulb', char: '💡' },
      { slug: 'anchor', char: '⚓' },
      { slug: 'infinity', char: '♾️' },
      { slug: 'recycle', char: '♻️' },
      { slug: 'no_entry', char: '⛔' },
      { slug: 'clock', char: '🕐' },
      { slug: 'hourglass', char: '⏳' },
      { slug: 'calendar', char: '📅' },
      { slug: 'pushpin', char: '📌' },
      { slug: 'link', char: '🔗' },
      { slug: 'mag', char: '🔍' },
      { slug: 'lock', char: '🔒' },
      { slug: 'key', char: '🔑' },
      { slug: 'bell', char: '🔔' },
      { slug: 'speech_balloon', char: '💬' },
      { slug: 'thought_balloon', char: '💭' },
      { slug: 'mailbox', char: '📬' },
      { slug: 'books', char: '📚' },
      { slug: 'newspaper', char: '📰' },
      { slug: 'art', char: '🎨' },
      { slug: 'clapper', char: '🎬' },
      { slug: 'video_game', char: '🎮' },
      { slug: 'dart', char: '🎯' },
      { slug: 'dice', char: '🎲' },
      { slug: 'camera', char: '📷' },
      { slug: 'tv', char: '📺' },
      { slug: 'computer', char: '💻' },
      { slug: 'iphone', char: '📱' },
      { slug: 'moneybag', char: '💰' },
      { slug: 'gift', char: '🎁' },
      { slug: 'balloon', char: '🎈' },
    ],
  },
  {
    name: 'Food & Drink',
    emoji: [
      { slug: 'coffee', char: '☕' },
      { slug: 'tea', char: '🍵' },
      { slug: 'beer', char: '🍺' },
      { slug: 'beers', char: '🍻' },
      { slug: 'wine_glass', char: '🍷' },
      { slug: 'cocktail', char: '🍸' },
      { slug: 'champagne', char: '🍾' },
      { slug: 'pizza', char: '🍕' },
      { slug: 'hamburger', char: '🍔' },
      { slug: 'taco', char: '🌮' },
      { slug: 'popcorn', char: '🍿' },
      { slug: 'cake', char: '🍰' },
      { slug: 'birthday', char: '🎂' },
      { slug: 'doughnut', char: '🍩' },
      { slug: 'cookie', char: '🍪' },
      { slug: 'apple', char: '🍎' },
      { slug: 'banana', char: '🍌' },
      { slug: 'watermelon', char: '🍉' },
      { slug: 'hot_pepper', char: '🌶️' },
      { slug: 'salt', char: '🧂' },
    ],
  },
  {
    name: 'Nature',
    emoji: [
      { slug: 'sunny', char: '☀️' },
      { slug: 'cloud', char: '☁️' },
      { slug: 'rain_cloud', char: '🌧️' },
      { slug: 'snowflake', char: '❄️' },
      { slug: 'rainbow', char: '🌈' },
      { slug: 'ocean', char: '🌊' },
      { slug: 'moon', char: '🌙' },
      { slug: 'earth_americas', char: '🌎' },
      { slug: 'seedling', char: '🌱' },
      { slug: 'evergreen_tree', char: '🌲' },
      { slug: 'cactus', char: '🌵' },
      { slug: 'rose', char: '🌹' },
      { slug: 'sunflower', char: '🌻' },
      { slug: 'four_leaf_clover', char: '🍀' },
      { slug: 'maple_leaf', char: '🍁' },
      { slug: 'dog', char: '🐶' },
      { slug: 'cat', char: '🐱' },
      { slug: 'bee', char: '🐝' },
      { slug: 'whale', char: '🐳' },
      { slug: 'penguin', char: '🐧' },
      { slug: 'unicorn', char: '🦄' },
      { slug: 'snake', char: '🐍' },
      { slug: 'owl', char: '🦉' },
    ],
  },
]

/** Every emoji, flattened — the order the groups are declared in. */
export const EMOJI: readonly EmojiEntry[] = EMOJI_GROUPS.flatMap((g) => g.emoji)

/**
 * Alternative spellings that resolve to a canonical entry.
 *
 * These are the codes people actually type out of Slack/GitHub habit; they are
 * searchable and substitutable but do not clutter the browse order with
 * duplicates of an emoji already listed above.
 */
const ALIASES: Readonly<Record<string, string>> = {
  '+1': 'thumbsup',
  '-1': 'thumbsdown',
  thumbs_up: 'thumbsup',
  thumbs_down: 'thumbsdown',
  grinning: 'smiley',
  smiley_face: 'smile',
  happy: 'smile',
  lol: 'joy',
  laugh: 'laughing',
  crying: 'sob',
  sad: 'cry',
  love: 'heart',
  hearts: 'heart',
  cool: 'sunglasses',
  think: 'thinking_face',
  thinking: 'thinking_face',
  hmm: 'thinking_face',
  mindblown: 'exploding_head',
  party: 'tada',
  celebrate: 'tada',
  party_parrot: 'partying_face',
  lit: 'fire',
  flame: 'fire',
  hundred: '100',
  perfect: '100',
  banger: 'fire',
  check: 'white_check_mark',
  cross: 'x',
  clapping: 'clap',
  applause: 'clap',
  hand: 'wave',
  hi: 'wave',
  bye: 'wave',
  rock_on: 'metal',
  horns: 'metal',
  music: 'notes',
  note: 'musical_note',
  song: 'musical_note',
  album: 'cd',
  vinyl: 'dvd',
  record: 'dvd',
  disc: 'cd',
  piano: 'musical_keyboard',
  keyboard: 'musical_keyboard',
  mic: 'microphone',
  drums: 'drum',
  sax: 'saxophone',
  listen: 'headphones',
  ears: 'ear',
  idea: 'bulb',
  ship: 'rocket',
  launch: 'rocket',
  bug: 'bee',
  gold: 'trophy',
  win: 'trophy',
  shrug_face: 'shrug',
  facepalm_face: 'facepalm',
  sun: 'sunny',
  rain: 'rain_cloud',
  snow: 'snowflake',
  beer_mug: 'beer',
  cheers: 'beers',
  wine: 'wine_glass',
  drink: 'cocktail',
  eyes_emoji: 'eyes',
  dead: 'skull',
  rip: 'skull',
  shh: 'speak_no_evil',
}

const BY_SLUG: ReadonlyMap<string, EmojiEntry> = new Map(EMOJI.map((e) => [e.slug, e]))

/**
 * A shortcode span. `+` and `-` are allowed so `:+1:` works, and the whole
 * thing is bounded so a stray colon in a long line cannot start a runaway scan.
 */
const SHORTCODE = /:([a-z0-9_+-]{1,32}):/gi

/** The emoji for a shortcode (with or without colons), or null if unknown. */
export function emojiFor(slug: string): string | null {
  const key = slug.replace(/^:|:$/g, '').toLowerCase()
  const canonical = ALIASES[key] ?? key
  return BY_SLUG.get(canonical)?.char ?? null
}

/**
 * Substitute every recognised `:shortcode:` in a string with its emoji.
 *
 * Unknown codes are left exactly as typed — this runs over whole message
 * bodies, so `12:30:45` and `http://x` have to survive untouched. Because
 * substitution is gated on resolving the code, they do.
 */
export function replaceShortcodes(text: string): string {
  return text.replace(SHORTCODE, (match, slug: string) => emojiFor(slug) ?? match)
}

/**
 * Emoji matching a partial shortcode, best match first.
 *
 * Prefix matches rank above substring matches so typing `:fire` offers 🔥
 * before anything that merely contains "fire". Aliases are searched too, and an
 * alias hit is reported under the canonical slug so the list never shows the
 * same emoji twice.
 */
export function searchEmoji(query: string, limit: number): EmojiEntry[] {
  const needle = query.toLowerCase()
  if (!needle) return EMOJI.slice(0, limit)

  const prefix: EmojiEntry[] = []
  const contains: EmojiEntry[] = []
  const seen = new Set<string>()

  const consider = (entry: EmojiEntry, matchedOn: string) => {
    if (seen.has(entry.slug)) return
    if (matchedOn.startsWith(needle)) {
      seen.add(entry.slug)
      prefix.push(entry)
    } else if (matchedOn.includes(needle)) {
      seen.add(entry.slug)
      contains.push(entry)
    }
  }

  for (const entry of EMOJI) consider(entry, entry.slug)
  for (const [alias, canonical] of Object.entries(ALIASES)) {
    const entry = BY_SLUG.get(canonical)
    if (entry) consider(entry, alias)
  }

  return [...prefix, ...contains].slice(0, limit)
}
