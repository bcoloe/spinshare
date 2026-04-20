import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { albumSearchService } from '../services/albumSearchService'
import type { AlbumSearchResult } from '../services/albumSearchService'

export function useAlbumSearch(query: string) {
  return useQuery({
    queryKey: ['albums', 'search', query],
    queryFn: () => albumSearchService.search(query),
    enabled: query.length >= 2,
  })
}

export function useGroupAlbums(groupId: number, status?: string) {
  return useQuery({
    queryKey: ['groups', groupId, 'albums', status ?? 'all'],
    queryFn: () => albumSearchService.getGroupAlbums(groupId, status),
    enabled: !!groupId,
  })
}

export function useNominateAlbum(groupId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (result: AlbumSearchResult) => {
      const album = await albumSearchService.getOrCreate(result)
      return albumSearchService.nominateToGroup(groupId, album.id)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['groups', groupId, 'albums'] }),
  })
}

export function useRemoveGroupAlbum(groupId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (groupAlbumId: number) =>
      albumSearchService.removeGroupAlbum(groupId, groupAlbumId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['groups', groupId, 'albums'] }),
  })
}
