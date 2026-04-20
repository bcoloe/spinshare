import { Button, Modal, Stack, Switch, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { useCreateGroup } from '../../hooks/useGroups'
import { ApiError } from '../../services/apiClient'

interface Props {
  opened: boolean
  onClose: () => void
}

interface FormValues {
  name: string
  is_public: boolean
}

export default function CreateGroupModal({ opened, onClose }: Props) {
  const createGroup = useCreateGroup()

  const form = useForm<FormValues>({
    initialValues: { name: '', is_public: true },
    validate: {
      name: (v) => {
        if (!v.trim()) return 'Name is required'
        if (v.length < 3 || v.length > 50) return '3–50 characters'
        if (!/^[A-Za-z0-9_-]+$/.test(v)) return 'Only letters, numbers, - and _'
        return null
      },
    },
  })

  const handleSubmit = async (values: FormValues) => {
    try {
      await createGroup.mutateAsync(values)
      notifications.show({ color: 'green', message: `Group "${values.name}" created` })
      form.reset()
      onClose()
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not create group'
      notifications.show({ color: 'red', message })
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title="Create group" centered>
      <form onSubmit={form.onSubmit(handleSubmit)}>
        <Stack gap="md">
          <TextInput
            label="Group name"
            placeholder="my-group"
            description="3–50 chars, letters/numbers/-/_"
            {...form.getInputProps('name')}
          />
          <Switch
            label="Public group"
            description="Anyone can search and join"
            {...form.getInputProps('is_public', { type: 'checkbox' })}
          />
          <Button type="submit" loading={createGroup.isPending}>
            Create
          </Button>
        </Stack>
      </form>
    </Modal>
  )
}
