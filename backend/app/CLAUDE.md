# CLAUDE.md (app)

## Directory Structure
* **models/**: SQLAlchemy ORM definitions. Each model has relationships defined via `relationship()`.
* **routers/**: FastAPI route handlers. Thin layer that delegates to services.
* **schemas/**: Pydantic models for request/response validation. Inherit from `BaseModel`.
* **services/**: Business logic layer. Primary location for feature implementation.
* **utils/**: Shared utilities (e.g., `security.py` for auth, password hashing).

## Creating New Features

### 1. Model (if new table needed)

```python
# models/thing.py
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Thing(Base):
    __tablename__ = "things"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))

    # Relationships
    user = relationship("User", back_populates="things")
```

Remember to:
- Add to `models/__init__.py` exports
- Create Alembic migration: `alembic revision --autogenerate -m "Add things table"`

### 2. Schema

```python
# schemas/thing.py
from pydantic import BaseModel, ConfigDict

class ThingBase(BaseModel):
    name: str

class ThingCreate(ThingBase):
    pass  # Add creation-specific fields

class ThingResponse(ThingBase):
    id: int
    model_config = ConfigDict(from_attributes=True)  # Enable ORM mode
```

### 3. Service

```python
# services/thing_service.py
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models import Thing
from app.schemas.thing import ThingCreate

class ThingService:
    def __init__(self, db: Session):
        self.db = db

    # ==================== CREATE ====================

    def create_thing(self, data: ThingCreate, user_id: int) -> Thing:
        """Create a new thing.

        Raises:
            HTTPException 409: If thing already exists
        """
        thing = Thing(name=data.name, user_id=user_id)
        self.db.add(thing)
        self.db.commit()
        self.db.refresh(thing)
        return thing
```

### 4. Tests

Tests live alongside source with `_test.py` suffix:

```python
# services/thing_service_test.py
import pytest
from fastapi import HTTPException, status

class TestThingServiceCreate:
    def test_create_thing_success(self, thing_service, sample_user):
        # Arrange
        data = ThingCreate(name="Test")

        # Act
        thing = thing_service.create_thing(data, sample_user.id)

        # Assert
        assert thing.name == "Test"
        assert thing.user_id == sample_user.id

    def test_create_thing_duplicate(self, thing_service, sample_user):
        # Test error cases with pytest.raises
        with pytest.raises(HTTPException) as exc_info:
            thing_service.create_thing(...)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
```

Add fixtures in `services/conftest.py`:
```python
@pytest.fixture
def thing_service(db_session):
    return ThingService(db_session)
```

## Key Utilities

### Security (`utils/security.py`)
- `hash_password(password)` → bcrypt hash
- `verify_password(plain, hashed)` → bool
- `validate_password_strength(password)` → (is_valid, reasons)
- `create_access_token(data)` / `create_refresh_token(data)`
- `decode_access_token(token)` / `decode_refresh_token(token)`

Password requirements: 8-50 chars, uppercase, lowercase, number, special char, no spaces.

### Config (`config.py`)
```python
from app.config import get_settings
settings = get_settings()  # Loads from .env
settings.DATABASE_URL
settings.SECRET_KEY
```

## Common Patterns

### Input Normalization
Emails and usernames are always lowercased:
```python
@field_validator("email", "username", mode="before")
@classmethod
def lowercase(cls, v):
    return v.lower() if v else v
```

### Handling IntegrityError
```python
from sqlalchemy.exc import IntegrityError

try:
    self.db.commit()
except IntegrityError:
    self.db.rollback()
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Constraint violation"
    ) from None
```