import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Anchor,
  Box,
  Button,
  Center,
  Paper,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { authService } from '../services/authService'
import { ApiError } from '../services/apiClient'

interface FormValues {
  email: string
}

export default function ForgotPasswordPage() {
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  const form = useForm<FormValues>({
    initialValues: { email: '' },
    validate: {
      email: (v) => (/^\S+@\S+\.\S+$/.test(v.trim()) ? null : 'Valid email required'),
    },
  })

  const handleSubmit = async (values: FormValues) => {
    setLoading(true)
    try {
      await authService.requestPasswordReset(values.email.trim().toLowerCase())
      setSubmitted(true)
    } catch (err) {
      // Surface unexpected errors; don't reveal whether the email exists.
      const message = err instanceof ApiError ? err.message : 'Something went wrong'
      notifications.show({ color: 'red', message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Center h="100vh">
      <Box w={380}>
        <Stack gap="xs" mb="xl">
          <Title order={2}>Reset your password</Title>
          <Text c="dimmed" size="sm">
            Enter your email and we'll send you a reset link.
          </Text>
        </Stack>

        <Paper withBorder p="xl" radius="md">
          {submitted ? (
            <Stack gap="sm">
              <Text size="sm">
                If that address is registered, a reset link is on its way. Check your inbox and
                follow the link — it expires in 30 minutes.
              </Text>
              <Text size="sm" c="dimmed">
                Didn't receive it? Check your spam folder or{' '}
                <Anchor component="button" onClick={() => setSubmitted(false)}>
                  try again
                </Anchor>
                .
              </Text>
            </Stack>
          ) : (
            <form onSubmit={form.onSubmit(handleSubmit)}>
              <Stack gap="md">
                <TextInput
                  label="Email"
                  placeholder="you@example.com"
                  autoComplete="email"
                  {...form.getInputProps('email')}
                />
                <Button type="submit" loading={loading} fullWidth mt="xs">
                  Send reset link
                </Button>
              </Stack>
            </form>
          )}
        </Paper>

        <Text size="sm" ta="center" mt="md" c="dimmed">
          Remember your password?{' '}
          <Anchor component={Link} to="/login">
            Sign in
          </Anchor>
        </Text>
      </Box>
    </Center>
  )
}
