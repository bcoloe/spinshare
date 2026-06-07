import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { exploreService } from '../services/exploreService'
import type {
  ExploreAlbumsPage,
  ExploreAlbumsParams,
  ExploreGroupsPage,
  ExploreGroupsParams,
} from '../types/explore'

export function useExploreAlbums(params: Omit<ExploreAlbumsParams, 'offset'> = {}) {
  return useInfiniteQuery({
    queryKey: [
      'explore',
      'albums',
      params.sort_by ?? 'top_rated',
      params.min_reviews ?? null,
      params.q ?? null,
    ],
    queryFn: ({ pageParam }) =>
      exploreService.getAlbums({ ...params, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage: ExploreAlbumsPage) => lastPage.next_offset ?? undefined,
    staleTime: 4 * 60 * 1000, // 4 min — backend caches pages for 5 min
  })
}

export function useExploreGroups(params: Omit<ExploreGroupsParams, 'offset'> = {}) {
  return useInfiniteQuery({
    queryKey: ['explore', 'groups', params.q ?? null, params.group_type ?? 'all'],
    queryFn: ({ pageParam }) => exploreService.getGroups({ ...params, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage: ExploreGroupsPage) => lastPage.next_offset ?? undefined,
  })
}

export function useSiteStats() {
  return useQuery({
    queryKey: ['explore', 'stats'],
    queryFn: () => exploreService.getSiteStats(),
    staleTime: 55 * 60 * 1000, // 55 min — backend caches for 1 hr; client refetches just before expiry
  })
}
