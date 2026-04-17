# spinshare

`spinshare` is a group-based music sharing web application with a randomized twist.

## Manifest

Music is fundamentally a shared experience. Not only between creator and listener, but also crucially between peer listeners. In this era of streaming, music is extremely accessible, but the turn towards data-driven recommendation algorithms removes a crucial component of the listening experience. While these algorithms are indeed quite good at offering recommendations, they are faceless and do not offer any grounding or means for discourse around the recommended albums. Instead of getting mixtapes that form a sort of window into someone's soul, we are getting bombarded with cold advertisement...

The goal of this project is to bring some of the soul back into the listening experience by enabling people to connect through thoughtful music sharing that encourages discussion and discovery.

## How it works?

_Listening groups_ are the core foundational unit of `spinshare` where users can join other users in sharing albums that they think are worth a spin. Each user within a given listening group is encouraged to review their personally curated music catalogs and nominate albums to share with the rest of the group. The nominated albums from all form a common group catalog, that can update over time as users nominate more albums. Each day, a random selection will be made from this group catalog and presented to all members of the group. This album is the spin of the day that each of the group members are to listen to, review, and guess who within the group nominated it.

As time goes on, users may nominate additional albums, update earlier reviews, and review stats to discover listening preferences.

---

## Development

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Node.js 18+ (for frontend)

### Getting Started

1. **Clone the repository**
   ```bash
   git clone https://github.com/bcoloe/spinshare.git
   cd spinshare
   ```

2. **Backend setup**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your database URL and secret key:
   #   DATABASE_URL=postgresql://user:pass@localhost/spinshare
   #   SECRET_KEY=<32+ character secret>
   ```

4. **Initialize database**
   ```bash
   alembic upgrade head
   ```

5. **Run tests**
   ```bash
   pytest
   ```

### Project Structure

```
spinshare/
├── backend/                # FastAPI + Python
│   ├── app/
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Business logic layer
│   │   ├── routers/        # API route handlers
│   │   └── utils/          # Shared utilities
│   ├── alembic/            # Database migrations
│   └── requirements.txt
├── frontend/               # React + TypeScript (planned)
└── DESIGN.md               # Architecture decisions
```

### Tech Stack

| Layer | Technology |
|-------|------------|
| Backend API | FastAPI |
| Database ORM | SQLAlchemy |
| Validation | Pydantic |
| Auth | JWT (python-jose) + bcrypt |
| Database | PostgreSQL |
| Frontend | React + TypeScript + Vite (planned) |
| UI Components | Mantine UI (planned) |

### Running the Development Server

```bash
cd backend
uvicorn app.main:app --reload
```

API documentation available at `http://localhost:8000/docs`

### Testing

Tests are co-located with source files using a `_test.py` suffix:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest app/services/user_service_test.py

# Run with coverage
pytest --cov=app
```

### Database Migrations

```bash
# Apply all migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "Add new table"

# Rollback one migration
alembic downgrade -1
```

### Contributing

See [CLAUDE.md](CLAUDE.md) for coding conventions and patterns used in this project.
