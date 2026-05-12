import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { albumService } from '../services/albumService'
import type { NominationGuessCreate, ReviewCreate, ReviewUpdate } from '../types/album'

export function useUpdateReview(albumId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reviewId, data }: { reviewId: number; data: ReviewUpdate }) =>
      albumService.updateReview(albumId, reviewId, data),
    onSuccess: (updated) => {
      qc.setQueryData(['reviews', albumId, 'me'], updated)
      qc.invalidateQueries({ queryKey: ['albums', albumId, 'reviews'] })
      qc.invalidateQueries({ queryKey: ['albums', albumId, 'stats'] })
      qc.invalidateQueries({
        predicate: (query) => {
          const key = query.queryKey as unknown[]
          return key[0] === 'groups' && key[2] === 'reviews'
        },
      })
    },
  })
}

export function useTodaysAlbums(groupId: number) {
  return useQuery({
    queryKey: ['groups', groupId, 'albums', 'today'],
    queryFn: () => albumService.getTodaysAlbums(groupId),
    enabled: !!groupId,
  })
}

export function useTriggerDailySelection(groupId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ forceChaos = false }: { forceChaos?: boolean } = {}) =>
      albumService.triggerDailySelection(groupId, forceChaos),
    onSuccess: (albums) => {
      qc.setQueryData(['groups', groupId, 'albums', 'today'], albums)
      qc.invalidateQueries({ queryKey: ['groups', groupId, 'nominations', 'count'] })
    },
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

export function useGuessOptions(groupId: number, groupAlbumId: number) {
  return useQuery({
    queryKey: ['guesses', groupId, groupAlbumId, 'options'],
    queryFn: () => albumService.getGuessOptions(groupId, groupAlbumId),
    enabled: !!groupId && !!groupAlbumId,
  })
}

export function useSubmitReview(albumId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ReviewCreate) => albumService.submitReview(albumId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['reviews', albumId, 'me'] })
      qc.invalidateQueries({ queryKey: ['albums', albumId, 'reviews'] })
      qc.invalidateQueries({ queryKey: ['albums', albumId, 'stats'] })
      qc.invalidateQueries({
        predicate: (query) => {
          const key = query.queryKey as unknown[]
          return key[0] === 'groups' && key[2] === 'reviews'
        },
      })
    },
  })
}

export function useCheckGuess(groupId: number, groupAlbumId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: NominationGuessCreate) =>
      albumService.checkGuess(groupId, groupAlbumId, data),
    onSuccess: (result) => {
      qc.setQueryData(['guesses', groupId, groupAlbumId, 'me'], result)
      qc.invalidateQueries({
        predicate: (query) => {
          const key = query.queryKey as unknown[]
          return key[0] === 'groups' && key[2] === 'guesses'
        },
      })
    },
  })
}
