# CLAUDE.md (backend)

## Directory Structure
* **alembic**: database versioning info, etc.
* **app**: core backend application logic.
* **scripts**: testing scripts and otherwise drivers to help with development and deployment.
* **.env***: environment files defining application-specific definitions.
* **requirements.txt**: central management of python dependencies to support backend execution.


### Data Model
users
- id (primary key)
- email (unique)
- password_hash
- username
- created_at

spotify_connections
- id (primary key)
- user_id (foreign key to users)
- spotify_user_id (Spotify's ID)
- access_token (encrypted)
- refresh_token (encrypted)
- token_expires_at
- last_refreshed_at

groups
- id
- name
- created_by (foreign key to users)
- created_at

group_members
- id
- group_id (foreign key)
- user_id (foreign key)
- joined_at

albums
- id
- spotify_album_id (unique)
- title
- artist
- cover_url
- cached metadata from Spotify
- added_at

group_albums
- id
- group_id
- album_id
- added_by (user_id)
- status (pending/selected/reviewed)
- selected_date (nullable)
- added_at

reviews
- id
- group_album_id
- user_id
- rating (optional)
- comment (optional)
- reviewed_at