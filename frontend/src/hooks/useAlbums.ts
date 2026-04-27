import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { albumSearchService } from '../services/albumSearchService'
import type { AlbumSearchParams, AlbumSearchResult } from '../services/albumSearchService'

export function useSpotifyLibrary(offset = 0) {
  return useQuery({
    queryKey: ['albums', 'library', offset],
    queryFn: () => albumSearchService.getLibraryAlbums(offset),
  })
}

export function useAlbumSearch(params: AlbumSearchParams) {
  const hasInput =
    (params.q?.length ?? 0) >= 2 ||
    (params.artist?.length ?? 0) >= 2 ||
    (params.album?.length ?? 0) >= 2
  return useQuery({
    queryKey: ['albums', 'search', params.q ?? '', params.artist ?? '', params.album ?? ''],
    queryFn: () => albumSearchService.search(params),
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
