export interface MetricPair {
  total: number
  recent: number
}

export interface TimeSeriesPoint {
  /** ISO date (YYYY-MM-DD). */
  day: string
  count: number
}

export interface AdminMetricsResponse {
  users: MetricPair
  groups: MetricPair
  albums: MetricPair
  reviews: MetricPair
  signups_by_day: TimeSeriesPoint[]
  reviews_by_day: TimeSeriesPoint[]
  open_link_reports: number
  window_days: number
}
