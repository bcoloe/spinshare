import { Alert, Stack, Text } from '@mantine/core'
import { IconCheck, IconX } from '@tabler/icons-react'
import type { CheckGuessResponse } from '../../types/album'

interface Props {
  result: CheckGuessResponse
}

export default function GuessResult({ result }: Props) {
  return (
    <Stack gap="xs">
      <Text size="sm" fw={600}>Your guess</Text>
      <Alert
        color={result.correct ? 'green' : 'red'}
        icon={result.correct ? <IconCheck size={16} /> : <IconX size={16} />}
        title={result.correct ? 'Correct!' : 'Not quite'}
      >
        This album was nominated by{' '}
        <Text span fw={600}>{result.nominator_username}</Text>.
      </Alert>
    </Stack>
  )
}
