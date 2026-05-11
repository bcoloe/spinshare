# Apple Music Integration Plan

## Context
SpinShare currently supports Spotify as the sole streaming platform (embedded playback, OAuth connection, album search). Users who subscribe to Apple Music instead of Spotify have no way to play albums within the app. This change adds parallel Apple Music support: an embedded MusicKit JS player, "Open in Apple Music" links, a per-user streaming service preference stored at the user level, and background cross-platform Apple Music ID resolution when albums are nominated.

Album search remains Spotify-only for now (follow-on task).

---

## Credentials Setup (prerequisite)
Before this works end-to-end, three values must be provisioned in the Apple Developer portal and added to `.env`:
- `APPLE_MUSIC_TEAM_ID` — 10-character Team ID from Apple Developer account
- `APPLE_MUSIC_KEY_ID` — Key ID of a MusicKit private key (created under Certificates, Identifiers & Profiles → Keys)
- `APPLE_MUSIC_PRIVATE_KEY` — Full contents of the generated `.p8` file (PEM-encoded)

---

## Backend

### 1. Config (`backend/app/config.py`)
Add three settings: `APPLE_MUSIC_TEAM_ID`, `APPLE_MUSIC_KEY_ID`, `APPLE_MUSIC_PRIVATE_KEY`.

### 2. Apple Music Client (`backend/app/utils/apple_music_client.py`) — new file
- `generate_developer_token() -> str` — ES256 JWT signed with the `.p8` private key; valid 180 days; cached until near-expiry (similar to `_get_client_token` in `spotify_client.py`)
- `AppleMusicAlbumResult` dataclass: `id, title, artist, release_date, cover_url, genres`
- `find_apple_music_album(title, artist, storefront="us") -> AppleMusicAlbumResult | None` — searches `/v1/catalog/{storefront}/search?types=albums&term=...`; picks best match using normalized title+artist comparison (reuse normalization pattern from `spotify_client.py`); returns `None` if no confident match
- Requires `PyJWT` and `cryptography` packages (add to `requirements.txt`)

### 3. Album Model (`backend/app/models/album.py`)
Add column: `apple_music_album_id = Column(String, nullable=True, unique=True, index=True)`

### 4. User Model (`backend/app/models/user.py`)
Add column: `preferred_streaming_service = Column(String, nullable=True)` — values: `"spotify"`, `"apple_music"`, or `NULL`

### 5. Schemas

**`backend/app/schemas/album.py`**
- Add `apple_music_album_id: Optional[str] = None` to `AlbumCreate`, `AlbumSearchResult`, and `AlbumResponse`

**`backend/app/schemas/user.py`**
- Add `preferred_streaming_service: Optional[str] = None` to user response + update schemas

### 6. Album Service (`backend/app/services/album_service.py`)
- `backfill_apple_music_id(db, album_id, title, artist)` — calls `apple_music_client.find_apple_music_album()`; if a match is found, updates the album row; no-op if `apple_music_album_id` already set or no match found
- `get_album_by_apple_music_id(db, id, raise_on_missing=True)` — mirrors `get_album_by_spotify_id`

### 7. User Service (`backend/app/services/user_service.py`)
- `set_streaming_preference(db, user_id, service)` — validates value is `"spotify"` or `"apple_music"`; updates user row
- `get_streaming_preference(db, user_id) -> str | None`

### 8. Albums Router (`backend/app/routers/albums.py`)
- `POST /albums/get-or-create`: inject `BackgroundTasks`; after successful creation (not on duplicate), schedule `backfill_apple_music_id` as a background task
- `GET /albums/apple-music/{apple_music_album_id}` — new endpoint, mirrors `/albums/spotify/{id}`

### 9. Users Router (`backend/app/routers/users.py`)
- `GET /users/apple-music/developer-token` — returns `{"developer_token": "..."}` using `apple_music_client.generate_developer_token()`; no auth required (developer token is public-facing, not user-specific)
- `PATCH /users/me/streaming-preference` — body `{"service": "apple_music"|"spotify"}`; calls `user_service.set_streaming_preference()`

### 10. Database Migration
Two columns via a single Alembic revision (use `/migrate-db` skill):
- `albums.apple_music_album_id` — `VARCHAR UNIQUE NULLABLE`
- `users.preferred_streaming_service` — `VARCHAR NULLABLE`

### 11. Tests
- `backend/app/utils/apple_music_client_test.py` — mock HTTP calls; test `find_apple_music_album` with match/no-match cases; test `generate_developer_token` format
- Update `backend/app/services/album_service_test.py` — cover `backfill_apple_music_id` and `get_album_by_apple_music_id`
- Update `backend/app/routers/albums_test.py` — cover background task scheduling on `get-or-create`
- Update `backend/app/routers/users_test.py` — cover developer-token and streaming-preference endpoints

---

## Frontend

### 1. Types
**`frontend/src/types/album.ts`** — add `apple_music_album_id: string | null` to `AlbumResponse` (and `GroupAlbumResponse` inherits it through the nested `album` field)

**`frontend/src/types/user.ts`** — add `preferred_streaming_service: 'spotify' | 'apple_music' | null`

### 2. API Service
Add to the existing API client:
- `getAppleMusicDeveloperToken(): Promise<string>`
- `updateStreamingPreference(service: 'spotify' | 'apple_music'): Promise<void>`

### 3. Apple Music Player Hook (`frontend/src/hooks/useAppleMusicPlayer.ts`) — new file
Mirrors the structure of `useSpotifyPlayer.ts`:
- Dynamically loads MusicKit JS from `https://js-cdn.music.apple.com/musickit/v3/musickit.js`
- Fetches developer token from backend, calls `MusicKit.configure()`
- Exposes: `status` (idle/loading/ready/playing/paused/not_connected/error), `authorize()`, `isAuthorized`, `playingAppleMusicAlbumId`, `position`, `duration`
- Controls: `togglePlay()`, `skipNext()`, `skipPrevious()`, `seekTo(ms)`, `startAlbum(appleMusicAlbumId)`

### 4. Player Context (`frontend/src/context/PlayerContext.tsx`)
- Instantiate both `useSpotifyPlayer()` and `useAppleMusicPlayer()`
- Add `activeService: 'spotify' | 'apple_music'` derived from `user.preferred_streaming_service` (fallback: `'spotify'` if Spotify is connected, else `'apple_music'`)
- `startAlbum()`: route to the appropriate underlying player based on `activeService`; if the album lacks an ID for the preferred service, fall back to the other service with a toast notification
- Expose `playingAlbumMeta` and controls regardless of which service is active

### 5. PlayerBar (`frontend/src/components/layout/PlayerBar.tsx`)
- Conditionally render player controls and metadata from the currently active service
- Show a small service icon (Spotify / Apple Music) to indicate which player is active

### 6. TodaysSpin and AlbumPage
**`frontend/src/components/spin/TodaysSpin.tsx`** and **`frontend/src/pages/AlbumPage.tsx`**:
- Add "Open in Apple Music" link: `https://music.apple.com/album/{apple_music_album_id}` (render only when `apple_music_album_id` is non-null)
- Play button uses `PlayerContext.startAlbum()` — already routes to correct service

### 7. Connect Apple Music UI
In the existing account settings/profile area (wherever the Spotify connect button lives):
- Add "Connect Apple Music" button → calls `useAppleMusicPlayer().authorize()` → on success, calls `updateStreamingPreference('apple_music')`
- Show connected state based on `useAppleMusicPlayer().isAuthorized`

---

## Out of Scope (follow-on)
- Album search across both platforms simultaneously
- Apple Music playlist/library management

---

## Verification
1. Add credentials to `.env` and run `alembic upgrade head`
2. `pytest backend/app/utils/apple_music_client_test.py` and `pytest backend/app/services/album_service_test.py`
3. Start backend; `GET /users/apple-music/developer-token` returns a valid JWT
4. Start frontend; navigate to settings, click "Connect Apple Music", complete MusicKit authorization
5. Nominate a Spotify album; verify background task resolves `apple_music_album_id` (check DB or `GET /albums/{id}` after a few seconds)
6. As an Apple Music user, verify the embedded player plays the album and "Open in Apple Music" link is present
7. As a Spotify user with no Apple Music ID on an album, verify "Open in Apple Music" link is hidden and Spotify player still works
