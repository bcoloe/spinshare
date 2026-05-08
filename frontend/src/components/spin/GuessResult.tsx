import { Alert, Stack, Text } from '@mantine/core'
import { IconCheck, IconX } from '@tabler/icons-react'
import type { CheckGuessResponse } from '../../types/album'

interface Props {
  result: CheckGuessResponse
}

function formatNominators(usernames: string[]): string {
  if (usernames.length === 1) return usernames[0]
  if (usernames.length === 2) return `${usernames[0]} and ${usernames[1]}`
  return `${usernames.slice(0, -1).join(', ')}, and ${usernames[usernames.length - 1]}`
}

export default function GuessResult({ result }: Props) {
  const revealText = result.is_chaos_selection
    ? 'This album was randomly added from outside the group.'
    : <>This album was nominated by <Text span fw={600}>{formatNominators(result.nominator_usernames)}</Text>.</>

  return (
    <Stack gap="xs">
      <Text size="sm" fw={600}>Your guess</Text>
      <Alert
        color={result.correct ? 'green' : 'red'}
        icon={result.correct ? <IconCheck size={16} /> : <IconX size={16} />}
        title={result.correct ? 'Correct!' : 'Not quite'}
      >
        {revealText}
      </Alert>
    </Stack>
  )
}
