import { useQuery } from '@tanstack/react-query'
import { artistService } from '../services/artistService'

export function useArtistOverview(name: string) {
  return useQuery({
    queryKey: ['artists', name],
    queryFn: () => artistService.getArtistOverview(name),
    enabled: !!name,
  })
}
