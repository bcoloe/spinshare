/** Route to an artist's overview page. Artist names may contain any character. */
export function artistPath(artist: string): string {
  return `/artists/${encodeURIComponent(artist)}`
}
