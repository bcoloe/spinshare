import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { albumSearchService } from '../services/albumSearchService'
import { albumService } from '../services/albumService'
import type { AlbumSearchPage, AlbumSearchParams, AlbumSearchResult } from '../services/albumSearchService'
import type { UserNominationResponse } from '../types/album'

export function useAlbumSearch(params: AlbumSearchParams) {
  const hasInput =
    (params.q?.length ?? 0) >= 2 ||
    (params.artist?.length ?? 0) >= 2 ||
    (params.album?.length ?? 0) >= 2
  return useInfiniteQuery({
    queryKey: ['albums', 'search', params.q ?? '', params.artist ?? '', params.album ?? ''],
    queryFn: ({ pageParam }) => albumSearchService.search({ ...params, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage: AlbumSearchPage) => lastPage.next_offset ?? undefined,
    enabled: hasInput,
  })
}

export function useGroupAlbums(groupId: number, status?: string) {
  return useQuery({
    queryKey: ['groups', groupId, 'albums', status ?? 'all'],
    queryFn: () => albumSearchService.getGroupAlbums(groupId, status),
    enabled: !!groupId,
  })
}

export function useMyNominations() {
  return useQuery<UserNominationResponse[]>({
    queryKey: ['users', 'me', 'nominations'],
    queryFn: () => albumSearchService.getMyNominations(),
  })
}

export function useNominateAlbum(groupId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (result: AlbumSearchResult) => {
      const album = await albumSearchService.getOrCreate(result)
      return albumSearchService.nominateToGroup(groupId, album.id)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['groups', groupId, 'albums'] })
      qc.invalidateQueries({ queryKey: ['users', 'me', 'nominations'] })
      qc.invalidateQueries({ queryKey: ['groups', groupId, 'nominations', 'count'] })
    },
  })
}

export function useNominateFromPool(groupId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (albumId: number) => albumSearchService.nominateToGroup(groupId, albumId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['groups', groupId, 'albums'] })
      qc.invalidateQueries({ queryKey: ['users', 'me', 'nominations'] })
      qc.invalidateQueries({ queryKey: ['groups', groupId, 'nominations', 'count'] })
    },
  })
}

export function useRemoveGroupAlbum(groupId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (groupAlbumId: number) =>
      albumSearchService.removeGroupAlbum(groupId, groupAlbumId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['groups', groupId, 'albums'] })
      qc.invalidateQueries({ queryKey: ['groups', groupId, 'nominations', 'count'] })
    },
  })
}

export function useNominationCount(groupId: number) {
  return useQuery({
    queryKey: ['groups', groupId, 'nominations', 'count'],
    queryFn: () => albumService.getNominationCount(groupId),
    enabled: !!groupId,
  })
}
