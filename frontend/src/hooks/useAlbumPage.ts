import { useQuery } from '@tanstack/react-query'
import { albumService } from '../services/albumService'

export function useAlbumDetails(albumId: number) {
  return useQuery({
    queryKey: ['albums', albumId],
    queryFn: () => albumService.getAlbumById(albumId),
    enabled: !!albumId,
  })
}

export function useAlbumReviews(albumId: number) {
  return useQuery({
    queryKey: ['albums', albumId, 'reviews'],
    queryFn: () => albumService.getAllReviews(albumId),
    enabled: !!albumId,
  })
}

export function useAlbumStats(albumId: number) {
  return useQuery({
    queryKey: ['albums', albumId, 'stats'],
    queryFn: () => albumService.getAlbumStats(albumId),
    enabled: !!albumId,
  })
}
