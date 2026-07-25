import { useQuery } from '@tanstack/react-query'
import { publicService } from '../services/publicService'

export function usePublicSpin() {
  return useQuery({
    queryKey: ['public', 'spin'],
    queryFn: () => publicService.getTodaysSpin(),
    staleTime: 5 * 60 * 1000,
  })
}
