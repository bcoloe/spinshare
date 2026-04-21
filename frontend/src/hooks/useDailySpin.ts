import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { albumService } from '../services/albumService'
import type { NominationGuessCreate, ReviewCreate } from '../types/album'

export function useUpdateReview(albumId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reviewId, data }: { reviewId: number; data: Partial<ReviewCreate> }) =>
      albumService.updateReview(albumId, reviewId, data),
    onSuccess: (updated) => qc.setQueryData(['reviews', albumId, 'me'], updated),
  })
}

export function useTodaysAlbums(groupId: number) {
  return useQuery({
    queryKey: ['groups', groupId, 'albums', 'today'],
    queryFn: () => albumService.getTodaysAlbums(groupId),
    enabled: !!groupId,
  })
}

export function useMyReview(albumId: number) {
  return useQuery({
    queryKey: ['reviews', albumId, 'me'],
    queryFn: () => albumService.getMyReview(albumId),
    enabled: !!albumId,
  })
}

export function useMyGuess(groupId: number, groupAlbumId: number) {
  return useQuery({
    queryKey: ['guesses', groupId, groupAlbumId, 'me'],
    queryFn: () => albumService.getMyGuess(groupId, groupAlbumId),
    enabled: !!groupId && !!groupAlbumId,
  })
}

export function useSubmitReview(albumId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ReviewCreate) => albumService.submitReview(albumId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reviews', albumId, 'me'] }),
  })
}

export function useCheckGuess(groupId: number, groupAlbumId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: NominationGuessCreate) =>
      albumService.checkGuess(groupId, groupAlbumId, data),
    onSuccess: (result) => {
      qc.setQueryData(['guesses', groupId, groupAlbumId, 'me'], result)
    },
  })
}
