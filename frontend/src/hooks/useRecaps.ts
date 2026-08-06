import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { recapService } from '../services/recapService'

export function useGroupRecaps(groupId: number, enabled: boolean = true) {
  return useQuery({
    queryKey: ['recaps', 'group', groupId],
    queryFn: () => recapService.listRecaps(groupId),
    enabled,
  })
}

export function usePendingRecaps(enabled: boolean) {
  return useQuery({
    queryKey: ['recaps', 'pending'],
    queryFn: () => recapService.getPending(),
    enabled,
  })
}

export function useMarkRecapSeen() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ groupId, recapId }: { groupId: number; recapId: number }) =>
      recapService.markSeen(groupId, recapId),
    onSuccess: (_data, { groupId }) => {
      qc.invalidateQueries({ queryKey: ['recaps', 'pending'] })
      qc.invalidateQueries({ queryKey: ['recaps', 'group', groupId] })
    },
  })
}
