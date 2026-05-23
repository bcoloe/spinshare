import { useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import {
  Anchor,
  Box,
  Button,
  Center,
  Paper,
  PasswordInput,
  Progress,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { authService } from '../services/authService'
import { ApiError } from '../services/apiClient'

interface FormValues {
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

export default function ResetPasswordPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''
  const [loading, setLoading] = useState(false)

  const form = useForm<FormValues>({
    initialValues: { password: '', confirmPassword: '' },
    validate: {
      password: validatePassword,
      confirmPassword: (v, values) =>
        v === values.password ? null : 'Passwords do not match',
    },
  })

  const strength = passwordStrength(form.values.password)

  if (!token) {
    return (
      <Center h="100vh">
        <Box w={380}>
          <Paper withBorder p="xl" radius="md">
            <Stack gap="sm">
              <Text fw={600}>Invalid reset link</Text>
              <Text size="sm" c="dimmed">
                This link is missing a reset token. Please request a new one.
              </Text>
              <Anchor component={Link} to="/forgot-password" size="sm">
                Request a new link
              </Anchor>
            </Stack>
          </Paper>
        </Box>
      </Center>
    )
  }

  const handleSubmit = async (values: FormValues) => {
    setLoading(true)
    try {
      await authService.confirmPasswordReset(token, values.password)
      notifications.show({ color: 'green', message: 'Password updated — please sign in.' })
      navigate('/login')
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Reset failed. The link may have expired — please request a new one.'
      notifications.show({ color: 'red', message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Center h="100vh">
      <Box w={380}>
        <Stack gap="xs" mb="xl">
          <Title order={2}>Choose a new password</Title>
          <Text c="dimmed" size="sm">
            Pick something strong — you'll use it to sign in going forward.
          </Text>
        </Stack>

        <Paper withBorder p="xl" radius="md">
          <form onSubmit={form.onSubmit(handleSubmit)}>
            <Stack gap="md">
              <div>
                <PasswordInput
                  label="New password"
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
                placeholder="Repeat your new password"
                autoComplete="new-password"
                {...form.getInputProps('confirmPassword')}
              />
              <Button type="submit" loading={loading} fullWidth mt="xs">
                Set new password
              </Button>
            </Stack>
          </form>
        </Paper>

        <Text size="sm" ta="center" mt="md" c="dimmed">
          Link expired?{' '}
          <Anchor component={Link} to="/forgot-password">
            Request a new one
          </Anchor>
        </Text>
      </Box>
    </Center>
  )
}
