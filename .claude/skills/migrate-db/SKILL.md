# migrate-db skill

Use this skill whenever you need to apply or create Alembic database migrations.

## Key facts

- `alembic` lives in `/home/brandon-coloe/miniconda3/bin/alembic` (conda PATH), **not** in the project `.venv`
- All `alembic` commands must be run from `backend/` (where `alembic.ini` lives)
- The `scripts/update_db.sh` helper creates **and** optionally upgrades in one step

## Applying pending migrations

**Always check the current head(s) first** before applying or writing a new migration file. Multiple heads cause `upgrade head` to fail.

```bash
# Step 1 — check state
cd /home/brandon-coloe/dev/spinshare/backend && alembic current && alembic heads

# Step 2 — if only one head, apply normally
cd /home/brandon-coloe/dev/spinshare/backend && alembic upgrade head

# Step 3 — if multiple heads exist, the new migration's down_revision must point
# to the current DB head (from `alembic current`), not the latest file in the
# versions/ directory. Fix the down_revision, then retry upgrade head.
```

Run this whenever the backend errors with `relation "..." does not exist` or similar `UndefinedTable` / `ProgrammingError` after a new migration file has been added.

### Writing a migration file manually

When writing the migration file by hand (instead of using autogenerate), set `down_revision` to the output of `alembic current`, not to the newest file in `alembic/versions/`. Those two can differ when branches are involved.

## Creating a new migration

### Auto-generate from model changes (preferred)

```bash
cd /home/brandon-coloe/dev/spinshare && scripts/update_db.sh "short description"
```

This generates the migration file only. Review and edit it before applying.

### Auto-generate AND apply immediately

```bash
cd /home/brandon-coloe/dev/spinshare && scripts/update_db.sh --force "short description"
```

### Manually (when the script isn't appropriate)

```bash
cd /home/brandon-coloe/dev/spinshare/backend && alembic revision --autogenerate -m "short description"
```

## Checking current state

```bash
# What revision is the DB at?
cd /home/brandon-coloe/dev/spinshare/backend && alembic current

# What migrations are pending?
cd /home/brandon-coloe/dev/spinshare/backend && alembic heads
```

## After applying migrations

If you just added a migration for a new table, verify it by running the backend tests:

```bash
cd /home/brandon-coloe/dev/spinshare && backend/scripts/test.sh -q --tb=short
```
