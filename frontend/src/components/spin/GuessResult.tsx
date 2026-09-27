import { Alert, Group, Stack, Text } from '@mantine/core'
import { IconCheck, IconX } from '@tabler/icons-react'
import { NominatorLinks } from '../albums/Nominators'
import type { CheckGuessResponse } from '../../types/album'

interface Props {
  result: CheckGuessResponse
}

export default function GuessResult({ result }: Props) {
  const guessedText = result.guess.guessed_user_id === null
    ? 'random (outside the group)'
    : result.guessed_username ?? 'Unknown'

  const revealText = result.is_chaos_selection
    ? 'This album was randomly added from outside the group.'
    : <>This album was nominated by <NominatorLinks usernames={result.nominator_usernames} />.</>

  return (
    <Stack gap="xs">
      <Text size="sm" fw={600}>Your guess</Text>
      <Alert
        color={result.correct ? 'green' : 'red'}
        icon={result.correct ? <IconCheck size={16} /> : <IconX size={16} />}
        title={result.correct ? 'Correct!' : 'Not quite'}
      >
        <Stack gap={4}>
          <Group gap={4}>
            <Text size="sm">You guessed:</Text>
            <Text size="sm" fw={600}>{guessedText}</Text>
          </Group>
          <Text size="sm">{revealText}</Text>
        </Stack>
      </Alert>
    </Stack>
  )
}
