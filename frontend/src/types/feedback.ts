export type FeedbackType = 'bug' | 'feature'

export interface FeedbackCreate {
  feedback_type: FeedbackType
  title: string
  description: string
}

export interface FeedbackResponse {
  issue_number: number
  issue_url: string
}
