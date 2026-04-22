# CLAUDE.md (frontend)

## Stack
- **Framework**: React + TypeScript (Vite)
- **UI**: Mantine v7
- **State**: React Query (`@tanstack/react-query`)
- **Icons**: `@tabler/icons-react`

## Key Directories

| Path | Purpose |
|------|---------|
| `src/pages/` | Top-level route pages |
| `src/components/` | Reusable UI components |
| `src/hooks/` | Custom React hooks |
| `src/services/` | API clients (backend + Spotify) |
| `src/context/` | React context providers (auth) |
| `src/types/` | TypeScript type declarations |

## Spotify Integration

All Spotify Web API calls go through `src/services/spotifyApiClient.ts`. The Spotify Web Playback SDK is initialised in `src/hooks/useSpotifyPlayer.ts`.

**Before implementing or modifying any Spotify API call, fetch the current endpoint documentation.** The API has had breaking changes (February 2026 endpoint consolidation) that are not in training data:

| Reference | URL |
|-----------|-----|
| Web API endpoints | https://developer.spotify.com/documentation/web-api/reference |
| Web Playback SDK | https://developer.spotify.com/documentation/web-playback-sdk/reference |
| API changelog | https://developer.spotify.com/documentation/web-api/references/changes |

### Known endpoint changes (February 2026)
- `/me/albums` (save/unsave/contains) → `/me/library` with `uris` query param
- `/playlists/{id}/tracks` → `/playlists/{id}/items`
- Playlist item response field `track` → `item`
- Max `limit` on playlist items: 50 (not 100)
