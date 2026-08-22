import type { ReactNode } from 'react'
import { Group, Paper, Text } from '@mantine/core'

interface StatCardProps {
  label: string
  value: number
  icon: ReactNode
  /** Optional secondary line, e.g. "+5 in 30d" on the admin dashboard. */
  delta?: string
}

export default function StatCard({ label, value, icon, delta }: StatCardProps) {
  return (
    <Paper withBorder p="md">
      <Group gap="sm" align="flex-start" wrap="nowrap">
        <Text c="dimmed">{icon}</Text>
        <div>
          <Text size="xl" fw={700} lh={1}>
            {value.toLocaleString()}
          </Text>
          <Text size="xs" c="dimmed" mt={4}>
            {label}
          </Text>
          {delta && (
            <Text size="xs" c="orange" mt={2}>
              {delta}
            </Text>
          )}
        </div>
      </Group>
    </Paper>
  )
}
