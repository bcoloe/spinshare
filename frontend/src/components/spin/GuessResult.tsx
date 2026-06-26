import { Alert, Anchor, Group, Stack, Text } from '@mantine/core'
import { IconCheck, IconX } from '@tabler/icons-react'
import { Link } from 'react-router-dom'
import type { CheckGuessResponse } from '../../types/album'

interface Props {
  result: CheckGuessResponse
}

function NominatorLinks({ usernames }: { usernames: string[] }) {
  const links = usernames.map((u) => (
    <Anchor key={u} component={Link} to={`/users/${u}`} fw={600} size="sm">
      {u}
    </Anchor>
  ))
  if (links.length === 1) return <>{links[0]}</>
  if (links.length === 2) return <>{links[0]} and {links[1]}</>
  return <>{links.slice(0, -1).reduce<React.ReactNode[]>((acc, l, i) => [...acc, l, <span key={`sep-${i}`}>, </span>], [])}, and {links[links.length - 1]}</>
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
