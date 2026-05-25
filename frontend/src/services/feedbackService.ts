import { apiFetch } from './apiClient'
import type { FeedbackCreate, FeedbackResponse } from '../types/feedback'

export const feedbackService = {
  submit(data: FeedbackCreate): Promise<FeedbackResponse> {
    return apiFetch('/feedback/', { method: 'POST', body: JSON.stringify(data) })
  },
}
