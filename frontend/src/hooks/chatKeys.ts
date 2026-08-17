/**
 * React Query keys for chat.
 *
 * Kept in their own module because both the socket context (which writes
 * incoming messages straight into the cache) and the chat hooks (which read it)
 * need them — importing one from the other would make the two files circular.
 */
export const chatKeys = {
  messages: (groupId: number) => ['chat', groupId, 'messages'] as const,
  presence: (groupId: number) => ['chat', groupId, 'presence'] as const,
  /** Unread counts for every group at once, keyed by group id. */
  unread: () => ['chat', 'unread'] as const,
}
