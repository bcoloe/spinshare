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
    staleTime: 25 * 60 * 1000, // 25 min — backend caches for 30 min; busted on review create/update/delete
  })
}
