import { useState } from 'react'
import { ActionIcon } from '@mantine/core'
import { IconSend } from '@tabler/icons-react'
import type { GroupMemberResponse } from '../../types/group'
import RichTextarea from '../common/RichTextarea'

const MAX_MESSAGE_LENGTH = 2000

interface Props {
  members: GroupMemberResponse[]
  onSend: (body: string) => void
  isSending: boolean
  disabled?: boolean
}

export default function MessageComposer({ members, onSend, isSending, disabled }: Props) {
  const [value, setValue] = useState('')

  const submit = () => {
    const body = value.trim()
    if (!body || isSending || disabled) return
    onSend(body)
    setValue('')
  }

  return (
    <RichTextarea
      value={value}
      onChange={setValue}
      members={members}
      onSubmit={submit}
      minRows={1}
      maxRows={5}
      maxLength={MAX_MESSAGE_LENGTH}
      placeholder={
        disabled ? 'Join this group to chat' : 'Message the group — @ to mention, : for emoji'
      }
      disabled={disabled}
      actions={
        <ActionIcon
          size="lg"
          radius="xl"
          variant="filled"
          color="violet"
          aria-label="Send message"
          disabled={disabled || !value.trim()}
          loading={isSending}
          onClick={submit}
        >
          <IconSend size={18} />
        </ActionIcon>
      }
    />
  )
}
