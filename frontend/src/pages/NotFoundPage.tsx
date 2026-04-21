import { Center, Stack, Text, Title } from '@mantine/core'

export default function NotFoundPage() {
  return (
    <Center h="100vh">
      <Stack align="center" gap="xs">
        <Title order={1} c="dimmed">404</Title>
        <Text c="dimmed">Page not found.</Text>
      </Stack>
    </Center>
  )
}
