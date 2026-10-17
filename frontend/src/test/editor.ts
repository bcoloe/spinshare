import { act, fireEvent } from '@testing-library/react'
import type { Editor } from '@tiptap/core'
import { docToMarkdown } from '../utils/richTextDoc'

/**
 * Helpers for tests that drive the rich text editor.
 *
 * jsdom has no real text input, so `user.type` can't exercise ProseMirror
 * faithfully. These go through the same hooks the browser does — the view's
 * `handleTextInput` (input rules, e.g. `**x**` → bold) and its keydown handling
 * (shortcuts, suggestions, submit) — so behaviour under test matches real use.
 */

/** The editor mounted in `container` (Tiptap hangs it off its DOM node). */
export function getEditor(container: ParentNode = document): Editor {
  const dom = container.querySelector('.ProseMirror') as (HTMLElement & { editor?: Editor }) | null
  if (!dom?.editor) throw new Error('No rich text editor rendered')
  return dom.editor
}

/** Type text at the selection, one character at a time, as a user would. */
export function typeText(editor: Editor, text: string) {
  act(() => {
    for (const ch of text) {
      const { from, to } = editor.state.selection
      const handled = editor.view.someProp('handleTextInput', (f) =>
        f(editor.view, from, to, ch, () => editor.state.tr.insertText(ch, from, to)),
      )
      if (!handled) editor.view.dispatch(editor.state.tr.insertText(ch, from, to))
    }
  })
}

/** Press a key in the editor (`{ ctrlKey: true }` etc. for chords). */
export function pressKey(editor: Editor, key: string, init: KeyboardEventInit = {}) {
  act(() => {
    fireEvent.keyDown(editor.view.dom, { key, ...init })
  })
}

/** Select the first occurrence of `text` in the document. */
export function selectText(editor: Editor, text: string) {
  let found: { from: number; to: number } | null = null
  editor.state.doc.descendants((node, pos) => {
    if (found || !node.isText) return
    const at = node.text!.indexOf(text)
    if (at !== -1) found = { from: pos + at, to: pos + at + text.length }
  })
  if (!found) throw new Error(`"${text}" not in the editor`)
  act(() => {
    editor.commands.setTextSelection(found!)
  })
}

/** What the editor would store right now. */
export function storedText(editor: Editor): string {
  return docToMarkdown(editor.state.doc)
}
