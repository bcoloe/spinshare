import type { GroupAlbumResponse } from '../types/album'
import type { GroupMemberResponse } from '../types/group'

/**
 * Usernames of every current member who nominated a group album, alphabetised.
 *
 * Co-nominations share one history row, so `nominator_user_ids` carries them all;
 * `added_by` is only the canonical (first) nominator. Nominators who have since
 * left the group are omitted, and chaos picks (no nominator) yield an empty list.
 */
export function nominatorUsernames(
  ga: Pick<GroupAlbumResponse, 'added_by' | 'nominator_user_ids'>,
  members: Pick<GroupMemberResponse, 'user_id' | 'username'>[],
): string[] {
  const ids = ga.nominator_user_ids.length > 0
    ? ga.nominator_user_ids
    : ga.added_by !== null ? [ga.added_by] : []
  const usernameById = new Map(members.map((m) => [m.user_id, m.username]))
  const usernames = new Set<string>()
  for (const id of ids) {
    const username = usernameById.get(id)
    if (username) usernames.add(username)
  }
  return [...usernames].sort((a, b) => a.localeCompare(b))
}
