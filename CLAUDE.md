# CLAUDE.md

The following provides some context on the overall `spinshare` project. There are additional CLAUDE.md files located at various levels of the repository providing additional scoped context to those areas.

## What is `spinshare`?
Spinshare is a web application where users can form groups and share albums for review among each other. The albums are selected from user nominations daily. See [README.md](README.md) for more information.

## Quick Start

```bash
# Backend development
cd backend
pip install -r requirements.txt
cp .env.example .env  # Configure DATABASE_URL, SECRET_KEY
pytest                # Run all tests

# Run specific test file
pytest app/services/user_service_test.py -v

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"
```

## Guiding Design Principles
`spinshare` is developed based on the following guiding principles:
1. **Prioritize maintenance**: design and code decisions should seek to minimize maintenance costs. This is to say that code should be modular, self-documenting, and clear in its intent, and that design decisions should favor common patterns and tooling.
2. **Defensive backend + restrictive frontend**: the backend routing should favor defensive coding strategies to encourage robustness. At the same time, frontend components and otherwise interaction points should minimize potential for bad input.
3. **Design for scalability**: although expectations are that this will not service large amounts of traffic, design decisions should favor eventual scaling.
4. **Minimal and sleek**: the application need not be bloated in order to be good. Focus on developing core functionality and presenting it in a clean and sleek fashion first. Frontend design shall focus on minimal, clean, and modern designs that use consistent styling.
5. **Test-driven**: a thoroughly tested backend shall ensure code quality and ultimately product safety.

## Key Conventions

- **Case sensitivity**: Emails and usernames are stored lowercase; use `.lower()` on input
- **Error handling**: Services raise `HTTPException` with appropriate status codes (see `backend/CLAUDE.md`)
- **Testing**: Tests live alongside source files with `_test.py` suffix (e.g., `user_service.py` / `user_service_test.py`)
- **Fixtures**: Hierarchical `conftest.py` files provide test fixtures at each level

## Repository Navigation

| Path | Purpose |
|------|---------|
| `backend/app/services/` | Business logic layer - start here for feature work |
| `backend/app/models/` | SQLAlchemy ORM definitions |
| `backend/app/schemas/` | Pydantic request/response schemas |
| `backend/app/routers/` | FastAPI endpoint definitions |
| `backend/app/utils/` | Shared utilities (security, helpers) |
| `.claude/skills/` | Claude Code skills for workflow automation |

## Supporting Files
| File | Description |
| ---- | ----------- |
| [README.md](README.md) | Developer-facing high level overview of the project. |
| [DESIGN.md](DESIGN.md) | High-level design and technology decisions. |

## External API References

When working with Spotify integrations, **always fetch the current documentation before implementing or modifying any Spotify Web API call**. The API has breaking changes (e.g. February 2026 endpoint consolidation) that are not reflected in training data.

| API | Reference URL |
|-----|--------------|
| Spotify Web API | https://developer.spotify.com/documentation/web-api/reference |
| Spotify Web Playback SDK | https://developer.spotify.com/documentation/web-playback-sdk/reference |
