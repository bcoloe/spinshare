# CLAUDE.md (backend)

## Directory Structure
* **alembic**: Database migrations. Run `alembic upgrade head` to apply, `alembic revision --autogenerate -m "msg"` to create.
* **app**: Core backend application logic (see `app/CLAUDE.md` for details).
* **scripts**: Testing scripts and development/deployment helpers.
* **.env***: Environment files. Requires `DATABASE_URL` and `SECRET_KEY` (min 32 chars).
* **requirements.txt**: Python dependencies.

## Installing Dependencies

**Always update `requirements.txt` first, then install via the venv** — never run `pip install` directly.

```bash
# After updating requirements.txt:
.venv/bin/pip install -r requirements.txt
```

## Running Tests

**Always use the `scripts/test.sh` wrapper** — never call `pytest` directly. It ensures the correct venv Python is used. Always run as a **foreground command** (never background/async).

```bash
# All tests
scripts/test.sh

# Specific file
scripts/test.sh app/routers/groups_test.py -v

# Specific class
scripts/test.sh app/routers/groups_test.py::TestGroupCreate -v

# Keyword filter
scripts/test.sh -k "test_create" -v

# Short output (faster feedback loop)
scripts/test.sh app/routers/groups_test.py -q --tb=short

# With coverage
scripts/test.sh --cov=app
```

Tests require `.env.test` with a test database URL.

### Router Test Fixtures

Router tests live in `app/routers/` and use `app/routers/conftest.py`:

| Fixture | Provides |
|---------|----------|
| `client` | `TestClient` with `get_db` overridden to use the test `db_session` |
| `registered_user` | A pre-created `User` object in the test DB |
| `auth_headers` | Bearer token headers for `registered_user` (generated via `create_access_token`, not the login endpoint) |
| `sample_group` | A public group owned by `registered_user` |

To authenticate as a different user in a test, call `_auth_headers_for(user)` from `app.routers.conftest`.

Do **not** call the `/users/login` HTTP endpoint in test fixtures — generate tokens directly.

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

## Testing Philosophy

Each layer has a distinct testing focus — use mocks liberally to isolate the layer under test:

| Layer | What to test | What to mock |
|-------|-------------|--------------|
| **Router** | HTTP status codes, request/response shapes, auth enforcement | The entire service (inject a `MagicMock`) |
| **Service** | Business logic, permission rules, DB mutations | External services (e.g. `user_service` calls from within `group_service`) |
| **Model** | ORM relationships, hybrid properties, constraints | Nothing — hit the test DB |

### Router tests — mock the service

Router tests should verify HTTP behaviour, not re-test business logic. Mock the service dependency so tests run fast and stay decoupled:

```python
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import get_group_service

def test_create_group_success(client, auth_headers):
    mock_service = MagicMock()
    mock_service.create_group.return_value = MagicMock(id=1, name="Bees", created_at=...)

    app.dependency_overrides[get_group_service] = lambda: mock_service
    resp = client.post("/groups/", json={"name": "Bees"}, headers=auth_headers)

    assert resp.status_code == 201
    mock_service.create_group.assert_called_once()
    app.dependency_overrides.pop(get_group_service)
```

For tests that need the real service (e.g. integration-style router tests), use the `client` fixture from `app/routers/conftest.py` which wires the real service against the test DB.

### Service tests — use the real DB, mock external calls

Service tests run against the test DB (via `db_session`). Mock only calls to *other* services or external APIs:

```python
from unittest.mock import patch

def test_something(sample_group_service, sample_group):
    with patch.object(sample_group_service, "some_external_call", return_value=...) as mock:
        result = sample_group_service.do_thing(sample_group.id)
    mock.assert_called_once()
```

### Avoid slow operations in router fixtures

User creation via `UserService.create_user` runs bcrypt (slow). In router tests that only need an authenticated user for the headers, generate the token directly:

```python
from app.routers.conftest import _auth_headers_for
# instead of creating a full user + calling login endpoint
headers = _auth_headers_for(some_user)
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