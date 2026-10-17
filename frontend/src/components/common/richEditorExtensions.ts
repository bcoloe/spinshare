import { Extension, InputRule, PasteRule, markInputRule, markPasteRule } from '@tiptap/core'
import type { Extensions } from '@tiptap/core'
import Document from '@tiptap/extension-document'
import Paragraph from '@tiptap/extension-paragraph'
import Text from '@tiptap/extension-text'
import HardBreak from '@tiptap/extension-hard-break'
import History from '@tiptap/extension-history'
import Placeholder from '@tiptap/extension-placeholder'
import Bold, {
  starInputRegex as boldStarInput,
  starPasteRegex as boldStarPaste,
} from '@tiptap/extension-bold'
import Italic, {
  starInputRegex as italicStarInput,
  starPasteRegex as italicStarPaste,
  underscoreInputRegex as italicUnderscoreInput,
  underscorePasteRegex as italicUnderscorePaste,
} from '@tiptap/extension-italic'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import Suggestion from '@tiptap/suggestion'
import type { SuggestionKeyDownProps } from '@tiptap/suggestion'
import { emojiFor } from '../../utils/emoji'
import { docToMarkdown } from '../../utils/richTextDoc'

/**
 * The rich editor's schema and behaviour, kept to exactly what the stored text
 * format can express: paragraphs, line breaks, bold and italic. Nothing else is
 * loaded, so markdown-ish typing like `# ` or `- ` stays plain text.
 */

// `**x**` for bold; `*x*` or `_x_` for italic. Tiptap's `__x__` bold shortcut
// is left out — the stored format has no double-underscore form. The underscore
// rule only fires after whitespace, so snake_case and usernames are safe.
const StarBold = Bold.extend({
  addInputRules() {
    return [markInputRule({ find: boldStarInput, type: this.type })]
  },
  addPasteRules() {
    return [markPasteRule({ find: boldStarPaste, type: this.type })]
  },
})

const StarItalic = Italic.extend({
  addInputRules() {
    return [
      markInputRule({ find: italicStarInput, type: this.type }),
      markInputRule({ find: italicUnderscoreInput, type: this.type }),
    ]
  },
  addPasteRules() {
    return [
      markPasteRule({ find: italicStarPaste, type: this.type }),
      markPasteRule({ find: italicUnderscorePaste, type: this.type }),
    ]
  },
})

// A shortcode must start a word: `1:100:5` is a ratio, not 1💯5.
const SHORTCODE_TYPED = /(?:^|\s)(:([a-z0-9_+-]{1,32}):)$/i
const SHORTCODE_PASTED = /(?:^|\s)(:([a-z0-9_+-]{1,32}):)/gi

/** Typed or pasted `:shortcode:` becomes its emoji, so Unicode is what gets stored. */
const EmojiShortcodes = Extension.create({
  name: 'emojiShortcodes',

  addInputRules() {
    return [
      new InputRule({
        find: SHORTCODE_TYPED,
        handler: ({ state, range, match }) => {
          const emoji = emojiFor(match[2])
          if (!emoji) return null
          // The match may include the whitespace before the ':'; keep it.
          const start = range.from + match[0].length - match[1].length
          state.tr.insertText(emoji, start, range.to)
        },
      }),
    ]
  },

  addPasteRules() {
    return [
      new PasteRule({
        find: SHORTCODE_PASTED,
        handler: ({ state, range, match }) => {
          const emoji = emojiFor(match[2])
          if (!emoji) return null
          const start = range.from + match[0].length - match[1].length
          state.tr.insertText(emoji, start, range.to)
        },
      }),
    ]
  },
})

/**
 * Refuse edits that would push the stored text past `maxLength`. The limit is
 * on the stored form (markers included), since that's what the server checks.
 * An edit that doesn't grow the text is always allowed, so loading content that
 * is already long — or deleting from it — can never be blocked.
 */
function maxLengthExtension(maxLength: number) {
  return Extension.create({
    name: 'maxStoredLength',
    addProseMirrorPlugins() {
      return [
        new Plugin({
          key: new PluginKey('maxStoredLength'),
          filterTransaction: (tr) => {
            if (!tr.docChanged) return true
            const next = docToMarkdown(tr.doc).length
            return next <= maxLength || next <= docToMarkdown(tr.before).length
          },
        }),
      ]
    },
  })
}

export interface SuggestionItem {
  key: string
  /** Text inserted in place of the trigger and query. */
  insert: string
  /** Leading glyph in the dropdown (the emoji itself, or nothing). */
  icon?: string
  label: string
}

/** What the component needs to show a suggestion list and act on it. */
export interface ActiveSuggestion {
  items: SuggestionItem[]
  select: (item: SuggestionItem) => void
}

export interface SuggestionHandlers {
  /** Called with the current list, or null when it closes. */
  onChange: (active: ActiveSuggestion | null) => void
  /** Arrow / Enter / Tab / Escape while a list is open. Return true if handled. */
  onKeyDown: (props: SuggestionKeyDownProps) => boolean
}

function suggestionExtension(
  name: string,
  char: string,
  items: (query: string) => SuggestionItem[],
  handlers: SuggestionHandlers,
) {
  return Extension.create({
    name,
    addProseMirrorPlugins() {
      return [
        Suggestion<SuggestionItem, SuggestionItem>({
          editor: this.editor,
          pluginKey: new PluginKey(name),
          char,
          items: ({ query }) => items(query),
          command: ({ editor, range, props }) => {
            editor.chain().focus().insertContentAt(range, `${props.insert} `).run()
          },
          render: () => {
            const report = (props: { items: SuggestionItem[]; command: (item: SuggestionItem) => void }) =>
              handlers.onChange(props.items.length ? { items: props.items, select: props.command } : null)
            return {
              onStart: report,
              onUpdate: report,
              onExit: () => handlers.onChange(null),
              onKeyDown: handlers.onKeyDown,
            }
          },
        }),
      ]
    },
  })
}

export interface EditorConfig {
  placeholder?: string
  maxLength: number
  /** `@handle` completions; omit to disable mentions. */
  mentionItems?: (query: string) => SuggestionItem[]
  emojiItems: (query: string) => SuggestionItem[]
  suggestions: SuggestionHandlers
}

export function editorExtensions(config: EditorConfig): Extensions {
  return [
    Document,
    Paragraph,
    Text,
    HardBreak,
    History,
    StarBold,
    StarItalic,
    EmojiShortcodes,
    Placeholder.configure({ placeholder: config.placeholder ?? '' }),
    maxLengthExtension(config.maxLength),
    suggestionExtension('emojiSuggestion', ':', config.emojiItems, config.suggestions),
    ...(config.mentionItems
      ? [suggestionExtension('mentionSuggestion', '@', config.mentionItems, config.suggestions)]
      : []),
  ]
}
