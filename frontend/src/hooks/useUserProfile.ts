import { useQuery } from '@tanstack/react-query'
import { userService } from '../services/userService'

export function useUserProfile(username: string) {
  return useQuery({
    queryKey: ['users', username, 'profile'],
    queryFn: () => userService.getProfile(username),
    enabled: !!username,
  })
}

export function useUserReviews(username: string) {
  return useQuery({
    queryKey: ['users', username, 'reviews'],
    queryFn: () => userService.getReviews(username),
    enabled: !!username,
  })
}

export function useUserNominationBreakdown(username: string) {
  return useQuery({
    queryKey: ['users', username, 'nominations', 'breakdown'],
    queryFn: () => userService.getNominationBreakdown(username),
    enabled: !!username,
  })
}
