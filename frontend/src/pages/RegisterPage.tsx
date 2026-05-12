import { useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import {
  Anchor,
  Box,
  Button,
  Center,
  Group,
  Paper,
  PasswordInput,
  Progress,
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
  username: string
  email: string
  first_name: string
  last_name: string
  password: string
  confirmPassword: string
}

function passwordStrength(password: string): number {
  if (!password) return 0
  let score = 0
  if (password.length >= 8) score++
  if (/[A-Z]/.test(password)) score++
  if (/[a-z]/.test(password)) score++
  if (/[0-9]/.test(password)) score++
  return (score / 4) * 100
}

const STRENGTH_COLOR = (pct: number) => {
  if (pct < 40) return 'red'
  if (pct < 80) return 'yellow'
  return 'green'
}

function validatePassword(v: string): string | null {
  if (v.length < 8) return 'At least 8 characters required'
  if (v.length > 50) return 'Maximum 50 characters'
  if (!/[A-Z]/.test(v)) return 'Must contain an uppercase letter'
  if (!/[a-z]/.test(v)) return 'Must contain a lowercase letter'
  if (!/[0-9]/.test(v)) return 'Must contain a number'
  if (/\s/.test(v)) return 'Must not contain spaces'
  return null
}

export default function RegisterPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [loading, setLoading] = useState(false)
  const next = searchParams.get('next')

  const form = useForm<FormValues>({
    initialValues: { username: '', email: '', first_name: '', last_name: '', password: '', confirmPassword: '' },
    validate: {
      username: (v) => {
        if (!v.trim()) return 'Username is required'
        if (v.length < 3 || v.length > 50) return '3–50 characters'
        if (!/^[A-Za-z0-9_-]+$/.test(v)) return 'Only letters, numbers, - and _'
        return null
      },
      email: (v) => (/^\S+@\S+\.\S+$/.test(v) ? null : 'Valid email required'),
      password: validatePassword,
      confirmPassword: (v, values) =>
        v === values.password ? null : 'Passwords do not match',
    },
  })

  const strength = passwordStrength(form.values.password)

  const handleSubmit = async (values: FormValues) => {
    setLoading(true)
    try {
      const registerPayload: Parameters<typeof authService.register>[0] = {
        username: values.username.trim().toLowerCase(),
        email: values.email.trim().toLowerCase(),
        password: values.password,
      }
      if (values.first_name.trim()) registerPayload.first_name = values.first_name.trim()
      if (values.last_name.trim()) registerPayload.last_name = values.last_name.trim()
      await authService.register(registerPayload)
      notifications.show({ color: 'green', message: 'Account created — please sign in' })
      navigate(next ? `/login?next=${encodeURIComponent(next)}` : '/login')
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Registration failed'
      notifications.show({ color: 'red', message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Center h="100vh">
      <Box w={400}>
        <Stack gap="xs" mb="xl">
          <Title order={2}>Create account</Title>
          <Text c="dimmed" size="sm">Join SpinShare</Text>
        </Stack>
        <Paper withBorder p="xl" radius="md">
          <form onSubmit={form.onSubmit(handleSubmit)}>
            <Stack gap="md">
              <TextInput
                label="Username"
                placeholder="your_username"
                description="3–50 chars, letters/numbers/-/_"
                autoComplete="username"
                {...form.getInputProps('username')}
              />
              <TextInput
                label="Email"
                placeholder="you@example.com"
                autoComplete="email"
                {...form.getInputProps('email')}
              />
              <Group gap="sm" grow>
                <TextInput
                  label="First name"
                  description="Optional"
                  placeholder="First name"
                  autoComplete="given-name"
                  maxLength={50}
                  {...form.getInputProps('first_name')}
                />
                <TextInput
                  label="Last name"
                  description="Optional"
                  placeholder="Last name"
                  autoComplete="family-name"
                  maxLength={50}
                  {...form.getInputProps('last_name')}
                />
              </Group>
              <div>
                <PasswordInput
                  label="Password"
                  placeholder="Create a strong password"
                  autoComplete="new-password"
                  {...form.getInputProps('password')}
                />
                {form.values.password && (
                  <Progress
                    value={strength}
                    color={STRENGTH_COLOR(strength)}
                    size="xs"
                    mt={4}
                  />
                )}
              </div>
              <PasswordInput
                label="Confirm password"
                placeholder="Repeat your password"
                autoComplete="new-password"
                {...form.getInputProps('confirmPassword')}
              />
              <Button type="submit" loading={loading} fullWidth mt="xs">
                Create account
              </Button>
            </Stack>
          </form>
        </Paper>
        <Text size="sm" ta="center" mt="md" c="dimmed">
          Already have an account?{' '}
          <Anchor component={Link} to="/login">
            Sign in
          </Anchor>
        </Text>
      </Box>
    </Center>
  )
}
