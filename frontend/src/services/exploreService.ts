import { apiFetch } from './apiClient'
import type {
  ExploreAlbumsPage,
  ExploreAlbumsParams,
  ExploreGroupsPage,
  ExploreGroupsParams,
  ExploreUsersPage,
  ExploreUsersParams,
  SiteStatsResponse,
} from '../types/explore'

export const exploreService = {
  getAlbums(params: ExploreAlbumsParams = {}): Promise<ExploreAlbumsPage> {
    const { offset = 0, limit = 20, min_reviews, sort_by, q } = params
    const qs = new URLSearchParams()
    qs.set('offset', String(offset))
    qs.set('limit', String(limit))
    if (min_reviews != null) qs.set('min_reviews', String(min_reviews))
    if (sort_by) qs.set('sort_by', sort_by)
    if (q) qs.set('q', q)
    return apiFetch(`/explore/albums?${qs}`)
  },

  getGroups(params: ExploreGroupsParams = {}): Promise<ExploreGroupsPage> {
    const { offset = 0, limit = 20, q, group_type } = params
    const qs = new URLSearchParams()
    qs.set('offset', String(offset))
    qs.set('limit', String(limit))
    if (q) qs.set('q', q)
    if (group_type) qs.set('group_type', group_type)
    return apiFetch(`/explore/groups?${qs}`)
  },

  getUsers(params: ExploreUsersParams = {}): Promise<ExploreUsersPage> {
    const { offset = 0, limit = 20, q } = params
    const qs = new URLSearchParams()
    qs.set('offset', String(offset))
    qs.set('limit', String(limit))
    if (q) qs.set('q', q)
    return apiFetch(`/explore/users?${qs}`)
  },

  getSiteStats(): Promise<SiteStatsResponse> {
    return apiFetch('/explore/stats')
  },
}
