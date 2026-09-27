import type { GroupDetailResponse } from '../types/group'

/**
 * Whether a group gets weekly recaps: only regular member groups do, not the
 * global group, bot groups, or dealer-mode groups (mirrors the recap generator).
 */
export function isRecapEligible(
  group: Pick<GroupDetailResponse, 'is_global' | 'is_bot_group' | 'settings'>,
): boolean {
  return !group.is_global && !group.is_bot_group && !group.settings?.dealer_mode
}
