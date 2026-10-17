import { Fragment } from 'react'
import type { ReactNode } from 'react'
import { Text } from '@mantine/core'
import { parseRichText } from '../../utils/richText'
import type { RichNode } from '../../utils/richText'

export interface RichTextMention {
  user_id: number
  username: string
}

interface Props {
  text: string
  /**
   * Server-resolved mentions. Only handles in this list are highlighted — the
   * text itself is never trusted for them, so an unresolvable or spoofed
   * `@handle` renders as the plain text it is.
   */
  mentions?: RichTextMention[]
  /** Highlights mentions of this user more strongly. */
  currentUsername?: string
}

/**
 * Render user-authored text with its `**bold**` / `*italic*` formatting and
 * resolved mentions.
 *
 * Output is built from React elements only — never HTML — so there is nothing
 * to sanitize: any markup in the text renders as literal characters.
 */
export default function RichText({ text, mentions = [], currentUsername }: Props) {
  const known = new Map(mentions.map((m) => [m.username.toLowerCase(), m]))

  const renderPlain = (plain: string, key: string): ReactNode => {
    if (known.size === 0) return <Fragment key={key}>{plain}</Fragment>

    // Split on handle-shaped runs, then keep only the ones the server confirmed.
    return plain.split(/(@[\w.-]+)/g).map((part, i) => {
      const mention = part.startsWith('@') ? known.get(part.slice(1).toLowerCase()) : undefined
      if (!mention) return <Fragment key={`${key}-${i}`}>{part}</Fragment>

      const isMe = currentUsername?.toLowerCase() === mention.username.toLowerCase()
      return (
        <Text
          key={`${key}-${i}`}
          span
          fw={600}
          c={isMe ? 'violet.3' : 'violet.5'}
          style={
            isMe
              ? {
                  background: 'var(--mantine-color-violet-9)',
                  borderRadius: 'var(--mantine-radius-sm)',
                  padding: '0 3px',
                }
              : undefined
          }
        >
          {part}
        </Text>
      )
    })
  }

  const renderNodes = (nodes: RichNode[], prefix: string): ReactNode[] =>
    nodes.map((node, i) => {
      const key = `${prefix}${i}`
      if (node.type === 'text') return renderPlain(node.text, key)
      const children = renderNodes(node.children, `${key}.`)
      return node.type === 'bold'
        ? <strong key={key}>{children}</strong>
        : <em key={key}>{children}</em>
    })

  return <>{renderNodes(parseRichText(text), '')}</>
}
