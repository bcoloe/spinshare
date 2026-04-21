import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  Anchor,
  Box,
  Button,
  Center,
  Paper,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { useAuth } from '../hooks/useAuth'
import { ApiError } from '../services/apiClient'

interface FormValues {
  identifier: string
  password: string
}

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)

  const form = useForm<FormValues>({
    initialValues: { identifier: '', password: '' },
    validate: {
      identifier: (v) => (v.trim() ? null : 'Email or username is required'),
      password: (v) => (v ? null : 'Password is required'),
    },
  })

  const handleSubmit = async (values: FormValues) => {
    setLoading(true)
    try {
      const identifier = values.identifier.trim().toLowerCase()
      const isEmail = identifier.includes('@')
      await login({
        ...(isEmail ? { email: identifier } : { username: identifier }),
        password: values.password,
      })
      navigate('/')
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Login failed'
      notifications.show({ color: 'red', message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Center h="100vh">
      <Box w={380}>
        <Stack gap="xs" mb="xl">
          <Title order={2}>Welcome back</Title>
          <Text c="dimmed" size="sm">Sign in to SpinShare</Text>
        </Stack>
        <Paper withBorder p="xl" radius="md">
          <form onSubmit={form.onSubmit(handleSubmit)}>
            <Stack gap="md">
              <TextInput
                label="Email or username"
                placeholder="you@example.com"
                autoComplete="username"
                {...form.getInputProps('identifier')}
              />
              <PasswordInput
                label="Password"
                placeholder="Your password"
                autoComplete="current-password"
                {...form.getInputProps('password')}
              />
              <Button type="submit" loading={loading} fullWidth mt="xs">
                Sign in
              </Button>
            </Stack>
          </form>
        </Paper>
        <Text size="sm" ta="center" mt="md" c="dimmed">
          No account?{' '}
          <Anchor component={Link} to="/register">
            Register
          </Anchor>
        </Text>
      </Box>
    </Center>
  )
}
