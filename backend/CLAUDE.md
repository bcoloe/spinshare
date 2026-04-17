# CLAUDE.md (backend)

## Directory Structure
* **alembic**: Database migrations. Run `alembic upgrade head` to apply, `alembic revision --autogenerate -m "msg"` to create.
* **app**: Core backend application logic (see `app/CLAUDE.md` for details).
* **scripts**: Testing scripts and development/deployment helpers.
* **.env***: Environment files. Requires `DATABASE_URL` and `SECRET_KEY` (min 32 chars).
* **requirements.txt**: Python dependencies.

## Running Tests

```bash
# All tests
pytest

# Specific test file
pytest app/services/user_service_test.py -v

# Specific test class
pytest app/services/user_service_test.py::TestUserServiceCreate -v

# With coverage
pytest --cov=app
```

Tests require `.env.test` with a test database URL.

## Service Layer Patterns

Services are the primary business logic layer. Follow these conventions:

```python
class ExampleService:
    def __init__(self, db: Session):
        self.db = db

    # CRUD operations grouped with comment headers
    # ==================== CREATE ====================
    def create_thing(self, data: ThingCreate) -> Thing:
        """Docstring with Raises section for HTTPExceptions"""
        # Validation, then create
        pass
```

### HTTP Exception Conventions
| Code | Usage |
|------|-------|
| 400 | Validation failures (e.g., weak password) |
| 401 | Authentication failures |
| 404 | Resource not found |
| 409 | Conflicts (duplicate email, username, constraint violations) |

### Error Raising Pattern
```python
from fastapi import HTTPException, status

# Always use status constants, not raw integers
raise HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="Email already registered"
)
```

## Test Fixtures

Fixtures are defined in hierarchical `conftest.py` files:

| File | Scope | Provides |
|------|-------|----------|
| `app/conftest.py` | Base | `db_session`, `test_settings`, `test_password` |
| `app/models/conftest.py` | Models | `sample_user`, `sample_album`, `creators` helper |
| `app/services/conftest.py` | Services | `sample_user_service`, `add_sample_user` |

The `creators` fixture provides a helper class for creating test entities:
```python
def test_example(creators, db_session):
    users = creators.users(["alice", "bob"])
    group = creators.group("Test Group", users[0])
```

## Data Model

### Core Tables
| Table | Key Fields | Notes |
|-------|------------|-------|
| `users` | id, email (unique), username (unique), password_hash | Lowercase email/username |
| `groups` | id, name, created_by (FK→users) | |
| `group_members` | group_id, user_id, joined_at | Association table |
| `albums` | id, spotify_album_id (unique), title, artist | Cached Spotify metadata |
| `group_albums` | group_id, album_id, added_by, status | pending/selected/reviewed |
| `reviews` | user_id, album_id, rating, comment | |
| `spotify_connections` | user_id, spotify_user_id, tokens | Encrypted tokens |

### Relationships
- User ↔ Group: Many-to-many via `group_members`
- User → Group: One-to-many via `created_by` (creator)
- Group → GroupAlbum → Album: Many-to-many with metadata
- User → Review → Album: User reviews albums