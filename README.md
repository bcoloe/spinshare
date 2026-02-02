# spinshare

music-groups/
├── frontend/                   # React + TypeScript
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   ├── auth/
│   │   │   ├── groups/
│   │   │   ├── albums/
│   │   │   └── common/
│   │   ├── pages/
│   │   │   ├── Login.tsx
│   │   │   ├── Register.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── GroupDetail.tsx
│   │   │   └── Profile.tsx
│   │   ├── hooks/
│   │   ├── services/           # API client code
│   │   │   ├── api.ts
│   │   │   ├── auth.ts
│   │   │   └── spotify.ts
│   │   ├── types/              # TypeScript interfaces
│   │   ├── utils/
│   │   ├── context/            # React context (auth state, etc)
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts          # or webpack config
│
├── backend/                    # FastAPI + Python
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI app entry point
│   │   ├── config.py          # Environment variables, settings
│   │   ├── database.py        # Database connection setup
│   │   ├── dependencies.py    # Dependency injection (get_current_user, etc)
│   │   │
│   │   ├── models/            # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── group.py
│   │   │   ├── album.py
│   │   │   └── spotify_connection.py
│   │   │
│   │   ├── schemas/           # Pydantic schemas for request/response
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── auth.py
│   │   │   ├── group.py
│   │   │   └── album.py
│   │   │
│   │   ├── routers/           # API route handlers
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── spotify.py
│   │   │   ├── groups.py
│   │   │   ├── albums.py
│   │   │   └── users.py
│   │   │
│   │   ├── services/          # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── spotify_service.py
│   │   │   ├── group_service.py
│   │   │   └── album_service.py
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── security.py    # Password hashing, JWT, encryption
│   │       └── spotify.py     # Spotify API helpers
│   │
│   ├── alembic/               # Database migrations
│   │   ├── versions/
│   │   └── env.py
│   ├── tests/
│   ├── requirements.txt       # or pyproject.toml
│   └── alembic.ini
│
├── scripts/                   # Utility scripts
│   └── daily_album_selector.py  # Cron job for daily selection
│
├── .env.example               # Template for environment variables
├── .gitignore
├── docker-compose.yml         # Optional: local dev environment
└── README.md


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