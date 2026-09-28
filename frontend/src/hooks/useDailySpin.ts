import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { QueryClient } from '@tanstack/react-query'
import { albumService } from '../services/albumService'
import type { NominationGuessCreate, ReviewCreate, ReviewResponse, ReviewUpdate } from '../types/album'

/**
 * Write a saved draft into the author's own cached copies, and nothing else.
 *
 * A draft is invisible to everyone but its author and counts toward no list,
 * average, stat, or credit, so invalidating those queries after an autosave
 * (every 3 s while typing) re-downloaded the group's whole history for nothing.
 */
function applyDraftToCache(qc: QueryClient, albumId: number, draft: ReviewResponse) {
  qc.setQueryData(['reviews', albumId, 'me'], draft)
  qc.setQueriesData<ReviewResponse[]>(
    {
      predicate: (query) => {
        const key = query.queryKey as unknown[]
        return key[0] === 'groups' && key[2] === 'reviews' && key[3] === 'me'
      },
    },
    (mine) => mine && [...mine.filter((r) => r.album_id !== albumId), draft],
  )
}

export function useUpdateReview(albumId: number, groupId?: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ reviewId, data }: { reviewId: number; data: ReviewUpdate }) =>
      albumService.updateReview(albumId, reviewId, data, groupId),
    onSuccess: (updated) => {
      if (updated.is_draft) {
        applyDraftToCache(qc, albumId, updated)
        return
      }
      qc.setQueryData(['reviews', albumId, 'me'], updated)
      qc.invalidateQueries({ queryKey: ['albums', albumId, 'reviews'] })
      qc.invalidateQueries({ queryKey: ['albums', albumId, 'stats'] })
      qc.invalidateQueries({
        predicate: (query) => {
          const key = query.queryKey as unknown[]
          return key[0] === 'groups' && key[2] === 'reviews'
        },
      })
      if (groupId != null) {
        qc.invalidateQueries({ queryKey: ['groups', groupId, 'albums', 'history'] })
        // Publishing a review may award a priority-pick credit.
        qc.invalidateQueries({ queryKey: ['groups', groupId, 'participation'] })
      }
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

export function useCatchUpAlbums(groupId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['groups', groupId, 'albums', 'catchup'],
    queryFn: () => albumService.getCatchUpAlbums(groupId),
    enabled: !!groupId && enabled,
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

export function useTodaysDeals(groupId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['groups', groupId, 'deals', 'today'],
    queryFn: () => albumService.getTodaysDeals(groupId),
    enabled: !!groupId && enabled,
  })
}

export function useRollDeal(groupId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => albumService.rollDeal(groupId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['groups', groupId, 'deals', 'today'] })
      qc.invalidateQueries({ queryKey: ['groups', groupId, 'albums', 'history'] })
      qc.invalidateQueries({ queryKey: ['groups', groupId, 'nominations', 'count'] })
    },
  })
}

export function useMyReview(albumId: number, enabled: boolean = true) {
  return useQuery({
    queryKey: ['reviews', albumId, 'me'],
    queryFn: () => albumService.getMyReview(albumId),
    enabled: !!albumId && enabled,
  })
}

export function useMyGuess(groupId: number, groupAlbumId: number, enabled: boolean = true) {
  return useQuery({
    queryKey: ['guesses', groupId, groupAlbumId, 'me'],
    queryFn: () => albumService.getMyGuess(groupId, groupAlbumId),
    enabled: !!groupId && !!groupAlbumId && enabled,
  })
}

export function useGuessOptions(groupId: number, groupAlbumId: number) {
  return useQuery({
    queryKey: ['guesses', groupId, groupAlbumId, 'options'],
    queryFn: () => albumService.getGuessOptions(groupId, groupAlbumId),
    enabled: !!groupId && !!groupAlbumId,
  })
}

export function useSubmitReview(albumId: number, groupId?: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ReviewCreate) => albumService.submitReview(albumId, data, groupId),
    onSuccess: (created) => {
      if (created.is_draft) {
        applyDraftToCache(qc, albumId, created)
        return
      }
      qc.invalidateQueries({ queryKey: ['reviews', albumId, 'me'] })
      qc.invalidateQueries({ queryKey: ['albums', albumId, 'reviews'] })
      qc.invalidateQueries({ queryKey: ['albums', albumId, 'stats'] })
      qc.invalidateQueries({
        predicate: (query) => {
          const key = query.queryKey as unknown[]
          return key[0] === 'groups' && key[2] === 'reviews'
        },
      })
      if (groupId != null) {
        qc.invalidateQueries({ queryKey: ['groups', groupId, 'albums', 'history'] })
        // Publishing a review may award a priority-pick credit.
        qc.invalidateQueries({ queryKey: ['groups', groupId, 'participation'] })
      }
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
      // Peer guesses are withheld until you've guessed — refetch now that they aren't.
      qc.invalidateQueries({ queryKey: ['stats', groupId, 'albums', groupAlbumId, 'guesses'] })
    },
  })
}
