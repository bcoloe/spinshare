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

export function useUserReviewStats(username: string) {
  return useQuery({
    queryKey: ['users', username, 'review-stats'],
    queryFn: () => userService.getReviewStats(username),
    enabled: !!username,
  })
}

export function useUserGroups(username: string) {
  return useQuery({
    queryKey: ['users', username, 'groups'],
    queryFn: () => userService.getGroups(username),
    enabled: !!username,
  })
}

export function useMyGroupActivity(enabled = true) {
  return useQuery({
    queryKey: ['users', 'me', 'group-activity'],
    queryFn: () => userService.getMyGroupActivity(),
    enabled,
  })
}
