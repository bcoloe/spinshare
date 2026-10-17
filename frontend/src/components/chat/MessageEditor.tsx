import { useState } from 'react'
import { Anchor, Group, Text } from '@mantine/core'
import type { GroupMemberResponse } from '../../types/group'
import RichTextarea from '../common/RichTextarea'

const MAX_MESSAGE_LENGTH = 2000

interface Props {
  initialBody: string
  members: GroupMemberResponse[]
  isSaving: boolean
  onSave: (body: string) => void
  onCancel: () => void
}

/** Inline editor for one of your own messages. Enter saves, Escape cancels. */
export default function MessageEditor({ initialBody, members, isSaving, onSave, onCancel }: Props) {
  const [value, setValue] = useState(initialBody)

  const save = () => {
    const body = value.trim()
    // Clearing a message is what delete is for; an empty edit just stays open.
    if (!body || isSaving) return
    if (body === initialBody) {
      onCancel()
      return
    }
    onSave(body)
  }

  return (
    <div>
      <RichTextarea
        value={value}
        onChange={setValue}
        members={members}
        onSubmit={save}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            e.preventDefault()
            onCancel()
          }
        }}
        autoFocus
        minRows={1}
        maxRows={5}
        maxLength={MAX_MESSAGE_LENGTH}
        size="sm"
        disabled={isSaving}
      />
      <Group gap={4} mt={2}>
        <Text size="xs" c="dimmed">
          Escape to{' '}
          <Anchor component="button" type="button" size="xs" onClick={onCancel}>
            cancel
          </Anchor>
          {' · '}Enter to{' '}
          <Anchor component="button" type="button" size="xs" onClick={save}>
            save
          </Anchor>
        </Text>
      </Group>
    </div>
  )
}
