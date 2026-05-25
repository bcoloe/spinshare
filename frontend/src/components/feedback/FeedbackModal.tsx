import { Anchor, Button, Modal, SegmentedControl, Stack, Text, Textarea, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { useSubmitFeedback } from '../../hooks/useFeedback'
import { ApiError } from '../../services/apiClient'
import type { FeedbackType } from '../../types/feedback'

interface Props {
  opened: boolean
  onClose: () => void
}

interface FormValues {
  feedback_type: FeedbackType
  title: string
  description: string
}

export default function FeedbackModal({ opened, onClose }: Props) {
  const submitFeedback = useSubmitFeedback()

  const form = useForm<FormValues>({
    initialValues: {
      feedback_type: 'bug',
      title: '',
      description: '',
    },
    validate: {
      title: (v) => {
        if (!v.trim()) return 'Title is required'
        if (v.length < 5) return 'At least 5 characters'
        if (v.length > 100) return 'Max 100 characters'
        return null
      },
      description: (v) => {
        if (!v.trim()) return 'Description is required'
        if (v.length < 20) return 'At least 20 characters'
        return null
      },
    },
  })

  const handleSubmit = async (values: FormValues) => {
    try {
      const result = await submitFeedback.mutateAsync(values)
      notifications.show({
        color: 'green',
        title: 'Feedback submitted',
        message: (
          <Text size="sm">
            Issue{' '}
            <Anchor href={result.issue_url} target="_blank" rel="noopener noreferrer">
              #{result.issue_number}
            </Anchor>{' '}
            created — thank you!
          </Text>
        ),
        autoClose: 8000,
      })
      form.reset()
      onClose()
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not submit feedback'
      notifications.show({ color: 'red', message })
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} title="Send feedback" centered>
      <form onSubmit={form.onSubmit(handleSubmit)}>
        <Stack gap="md">
          <SegmentedControl
            fullWidth
            data={[
              { label: 'Bug / Issue', value: 'bug' },
              { label: 'Feature Request', value: 'feature' },
            ]}
            {...form.getInputProps('feedback_type')}
          />
          <TextInput
            label="Title"
            placeholder="Brief summary (5–100 chars)"
            {...form.getInputProps('title')}
          />
          <Textarea
            label="Description"
            placeholder="Describe the issue or feature in detail (min 20 chars)"
            minRows={4}
            autosize
            {...form.getInputProps('description')}
          />
          <Button type="submit" loading={submitFeedback.isPending}>
            Submit
          </Button>
        </Stack>
      </form>
    </Modal>
  )
}
