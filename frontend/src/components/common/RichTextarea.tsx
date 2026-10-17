import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { Group, Input, Paper, Stack, Text, UnstyledButton } from '@mantine/core'
import type { MantineSize } from '@mantine/core'
import { RichTextEditor } from '@mantine/tiptap'
import { IconBold, IconItalic } from '@tabler/icons-react'
import { useEditor } from '@tiptap/react'
import { searchEmoji } from '../../utils/emoji'
import { docToMarkdown, markdownToDoc } from '../../utils/richTextDoc'
import type { GroupMemberResponse } from '../../types/group'
import EmojiPicker from './EmojiPicker'
import { editorExtensions } from './richEditorExtensions'
import type { ActiveSuggestion } from './richEditorExtensions'

const MAX_SUGGESTIONS = 6
// The editable area's line height (see styles.css), so `minRows` / `maxRows`
// size the box like the textarea this replaced.
const LINE_HEIGHT_EM = 1.55

const IS_MAC = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)
const MOD_KEY = IS_MAC ? '⌘' : 'Ctrl+'

interface Props {
  /** Stored text: `**bold**` / `*italic*` markers, one line per paragraph. */
  value: string
  onChange: (value: string) => void
  /**
   * Members offered by `@` autocomplete. Omit to disable mentions entirely —
   * reviews do, since mentioning someone there would point them at a review
   * they may not be allowed to see yet.
   */
  members?: GroupMemberResponse[]
  /** When set, Enter submits and Shift+Enter inserts a line break. */
  onSubmit?: () => void
  /** Rendered beside the editor, e.g. a send button. */
  actions?: ReactNode
  label?: string
  placeholder?: string
  /** Limit on the stored text, markers included — what the server enforces. */
  maxLength: number
  minRows?: number
  maxRows?: number
  size?: MantineSize
  disabled?: boolean
}

/**
 * The text editor shared by chat and review comments.
 *
 * Formatting shows as formatting, not markers: typing `**word**` or `*word*`
 * turns it bold or italic on the spot, as do the toolbar buttons and
 * Ctrl/Cmd+B / Ctrl/Cmd+I. `:shortcode:` becomes its emoji, with autocomplete
 * and a picker, and — when `members` is given — `@handle` autocompletes.
 *
 * The value going in and out is still plain stored text (see `richText.ts`),
 * so nothing that saves or renders it needs to know an editor is involved.
 */
export default function RichTextarea({
  value,
  onChange,
  members,
  onSubmit,
  actions,
  label,
  placeholder,
  maxLength,
  minRows = 2,
  maxRows,
  size,
  disabled,
}: Props) {
  const labelId = useId()
  const [suggestion, setSuggestion] = useState<ActiveSuggestion | null>(null)
  const [highlighted, setHighlighted] = useState(0)

  // The editor's extensions are built once; everything they call back into is
  // read through refs so it always sees the current props and state.
  const latest = useRef({ onChange, onSubmit, members, suggestion, highlighted })
  latest.current = { onChange, onSubmit, members, suggestion, highlighted }
  // The last value this editor emitted, to tell our own echo from a real
  // outside change (a cleared composer, a restored draft).
  const emitted = useRef(value)
  const hasMentions = !!members

  const extensions = useMemo(
    () =>
      editorExtensions({
        placeholder,
        maxLength,
        emojiItems: (query) =>
          // Two characters before offering anything: a lone ':' is far too
          // common in prose, timestamps and URLs to open a picker for.
          query.length < 2
            ? []
            : searchEmoji(query, MAX_SUGGESTIONS).map((e) => ({
                key: `emoji-${e.slug}`,
                insert: e.char,
                icon: e.char,
                label: `:${e.slug}:`,
              })),
        // The roster is read through `latest`, so a membership change doesn't
        // rebuild the editor; only whether mentions exist at all does.
        mentionItems: hasMentions
          ? (query) =>
              (latest.current.members ?? [])
                .filter((m) => m.username.toLowerCase().startsWith(query.toLowerCase()))
                .slice(0, MAX_SUGGESTIONS)
                .map((m) => ({
                  key: `mention-${m.user_id}`,
                  insert: `@${m.username}`,
                  label: `@${m.username}`,
                }))
          : undefined,
        suggestions: {
          onChange: (active) => {
            setSuggestion(active)
            setHighlighted(0)
          },
          onKeyDown: ({ event }) => {
            const { suggestion: active, highlighted: index } = latest.current
            if (!active) return false
            const count = active.items.length
            if (event.key === 'ArrowDown') {
              setHighlighted((index + 1) % count)
              return true
            }
            if (event.key === 'ArrowUp') {
              setHighlighted((index - 1 + count) % count)
              return true
            }
            if (event.key === 'Enter' || event.key === 'Tab') {
              active.select(active.items[index])
              return true
            }
            if (event.key === 'Escape') {
              // Hidden until the query next changes, which reports a fresh list.
              setSuggestion(null)
              return true
            }
            return false
          },
        },
      }),
    [placeholder, maxLength, hasMentions],
  )

  const editor = useEditor(
    {
      extensions,
      content: markdownToDoc(value),
      editable: !disabled,
      editorProps: {
        attributes: {
          role: 'textbox',
          'aria-multiline': 'true',
          ...(label ? { 'aria-labelledby': labelId } : { 'aria-label': placeholder ?? 'Text' }),
        },
        handleKeyDown: (_view, event) => {
          // An open suggestion list owns Enter; its plugin handles it next.
          if (latest.current.suggestion) return false
          const submit = latest.current.onSubmit
          if (submit && event.key === 'Enter' && !event.shiftKey) {
            submit()
            return true
          }
          return false
        },
      },
      onUpdate: ({ editor: current }) => {
        // Only real edits count: Tiptap also emits "update" for things like an
        // editable toggle, and draft autosave treats any onChange as typing.
        const next = docToMarkdown(current.state.doc)
        if (next === emitted.current) return
        emitted.current = next
        latest.current.onChange(next)
      },
    },
    [extensions],
  )

  // Outside changes (send clears the composer; autosave restores a draft).
  useEffect(() => {
    if (!editor || value === emitted.current) return
    emitted.current = value
    editor.commands.setContent(markdownToDoc(value), false)
  }, [editor, value])

  useEffect(() => {
    // emitUpdate false: toggling editability is not an edit.
    editor?.setEditable(!disabled, false)
  }, [editor, disabled])

  const insertEmoji = (char: string) => {
    editor?.chain().focus().insertContent(char).run()
  }

  return (
    <Input.Wrapper
      label={label}
      size={size}
      labelProps={{ id: labelId, onClick: () => editor?.commands.focus() }}
    >
      <Stack gap={4} style={{ position: 'relative' }}>
        {suggestion && (
          <Paper
            withBorder
            radius="sm"
            shadow="md"
            p={4}
            style={{ position: 'absolute', bottom: '100%', left: 0, right: 0, zIndex: 3 }}
          >
            <Stack gap={0}>
              {suggestion.items.map((item, i) => (
                <UnstyledButton
                  key={item.key}
                  onMouseDown={(e) => {
                    // mousedown, not click — click would blur the editor first.
                    e.preventDefault()
                    suggestion.select(item)
                  }}
                  onMouseEnter={() => setHighlighted(i)}
                  p="xs"
                  style={{
                    borderRadius: 'var(--mantine-radius-sm)',
                    background: i === highlighted ? 'var(--mantine-color-dark-5)' : 'transparent',
                  }}
                >
                  <Group gap="xs" wrap="nowrap">
                    {item.icon && <Text size="sm">{item.icon}</Text>}
                    <Text size="sm" truncate>
                      {item.label}
                    </Text>
                  </Group>
                </UnstyledButton>
              ))}
            </Stack>
          </Paper>
        )}

        <Group gap={4} align="flex-end" wrap="nowrap">
          {/* One bordered box: a formatting bar over the text, as in Slack. */}
          <RichTextEditor
            editor={editor}
            variant="subtle"
            className="rich-textarea"
            flex={1}
            style={{
              minWidth: 0,
              // Sizing for the editable area, applied in styles.css.
              '--rich-textarea-font-size': `var(--mantine-font-size-${size ?? 'sm'})`,
              '--rich-textarea-min-height': `${minRows * LINE_HEIGHT_EM}em`,
              '--rich-textarea-max-height': maxRows ? `${maxRows * LINE_HEIGHT_EM}em` : 'none',
            } as CSSProperties}
          >
            <RichTextEditor.Toolbar p={2}>
              {/* Generic controls rather than RichTextEditor.Bold / .Italic,
                  which overwrite `disabled` with their own can-run check. */}
              <RichTextEditor.ControlsGroup>
                <RichTextEditor.Control
                  aria-label="Bold"
                  title={`Bold (${MOD_KEY}B)`}
                  active={!!editor?.isActive('bold')}
                  disabled={disabled}
                  onClick={() => editor?.chain().focus().toggleBold().run()}
                >
                  <IconBold size={15} />
                </RichTextEditor.Control>
                <RichTextEditor.Control
                  aria-label="Italic"
                  title={`Italic (${MOD_KEY}I)`}
                  active={!!editor?.isActive('italic')}
                  disabled={disabled}
                  onClick={() => editor?.chain().focus().toggleItalic().run()}
                >
                  <IconItalic size={15} />
                </RichTextEditor.Control>
              </RichTextEditor.ControlsGroup>
              <EmojiPicker onSelect={insertEmoji} disabled={disabled} />
            </RichTextEditor.Toolbar>
            <RichTextEditor.Content />
          </RichTextEditor>
          {actions}
        </Group>
      </Stack>
    </Input.Wrapper>
  )
}
