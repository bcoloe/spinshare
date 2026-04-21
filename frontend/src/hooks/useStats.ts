import { useQuery } from '@tanstack/react-query'
import { statsService } from '../services/statsService'

export function useMyStats() {
  return useQuery({
    queryKey: ['stats', 'me'],
    queryFn: () => statsService.getMyStats(),
  })
}

export function useMyGuessStats(groupId: number, userId: number) {
  return useQuery({
    queryKey: ['stats', 'guesses', groupId, userId],
    queryFn: () => statsService.getMyGuessStats(groupId, userId),
    enabled: !!groupId && !!userId,
  })
}
