import { useMutation } from '@tanstack/react-query'
import { feedbackService } from '../services/feedbackService'
import type { FeedbackCreate } from '../types/feedback'

export function useSubmitFeedback() {
  return useMutation({
    mutationFn: (data: FeedbackCreate) => feedbackService.submit(data),
  })
}
