# DESIGN.md

This document captures various design decisions, project layout, and guiding principles for designing `spinshare`.

## Structure

`spinshare` adheres to a standard web 


### Repo Structure
```
spinshare/
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
│   └── daily_album_selector.py  # Manual daily selection (scheduled in-process; see backend/scripts/scheduled_jobs.md)
│
├── .env.example               # Template for environment variables
├── .gitignore
├── docker-compose.yml         # Optional: local dev environment
└── README.md
```




## Tools

### Backend
The backend logic is implemented with python leaning on `sqlalchemy` for database definitions and interactions, `fastapi` for endpoint routing definitions, `pydantic` for schema definition, and `passlib` + `jose` for security. The application uses a postgres database for maintaining all relevant data. Unit tests are written using `pytest`.

### Frontend
The frontend logic is implemented in typescript using a React framework built via Vite. Components are pulled from Mantine UI.

