# Scheduled jobs: daily album selection and weekly recap

Both jobs run **inside the API process** (`app/scheduler.py`), started from the
FastAPI lifespan. There is no crontab or systemd timer to install.

## How it works

Once a minute the scheduler checks, from memory, whether any group is due:

| Job | Due when | Idempotent per |
|-----|----------|----------------|
| Daily selection | the group's local clock reaches `DAILY_SELECTION_HOUR` on one of its `selection_days` | group-local day |
| Weekly recap | the group's local Monday reaches `WEEKLY_RECAP_HOUR` (recap-eligible groups only) | group-local week |

The database is opened only when something is due, or when the in-memory map of
group schedules needs reloading (at startup, and within a minute of any committed
change to a group, its settings, or its bot sources). An idle tick costs nothing.

After a restart the first tick catches up anything missed while the process was
down. That is safe because both jobs are idempotent.

Outcomes, per group:

- **done** — finished for the day or week.
- **rejected** — the service refused, for example because the nomination pool is
  empty. This is also final for the day; retrying would only wake the database.
- **failed** — an unexpected error. The group is retried after an hour.

## Configuration (`backend/.env`)

| Setting | Default | Meaning |
|---------|---------|---------|
| `SCHEDULER_ENABLED` | `true` | Set `false` to stop the API from scheduling (tests and profiling do this) |
| `DAILY_SELECTION_HOUR` | `1` | Group-local hour (0–23) at which the daily spin is drawn |
| `WEEKLY_RECAP_HOUR` | `4` | Group-local hour on Monday at which last week's recap is generated |

The defaults reproduce the crontab this replaced (`0 1 * * *` and `0 4 * * 1` on
an America/New_York server) for groups in that timezone. Groups in other
timezones now roll over on their own clock.

## Observability

- `GET /admin/scheduler` (admin only, served from memory) shows:
  - whether the scheduler is running, plus its last tick and last error;
  - the most recent runs;
  - for each group: the day and week it last ran, when it is next due, and any
    pending retry.
- Rejections and failures are logged at WARNING/ERROR to the API's journal (`journalctl -u spinshare-api`). Successful runs are logged at INFO, which uvicorn's default logging hides, so `/admin/scheduler` is the record of those.

## Running a job by hand

The CLI scripts call the same code (`app/services/scheduled_jobs.py`). Running one
alongside the scheduler is harmless.

```bash
cd /opt/spinshare/backend
.venv/bin/python scripts/daily_album_selector.py              # every group
.venv/bin/python scripts/daily_album_selector.py --group 42   # one group
.venv/bin/python scripts/daily_album_selector.py --n 3        # override the count
.venv/bin/python scripts/weekly_recap_generator.py            # every due group
.venv/bin/python scripts/weekly_recap_generator.py --group 42 --week-start 2026-07-27          # backfill
.venv/bin/python scripts/weekly_recap_generator.py --group 42 --week-start 2026-07-27 --force  # regenerate
```

`daily_album_selector.py` exits non-zero if any group was rejected or failed.

## Migrating off the crontab

1. Deploy this version. The scheduler starts with the API.
2. Check `GET /admin/scheduler`: `running` is true, `schedule_loaded` is true, and
   each group has a sensible `next_selection_at`.
3. Remove the two spinshare entries from the `spinshare` user's crontab (`crontab -e`).
   Running both for a while does no harm, because the jobs are idempotent.

## Scaling note

Only one process may run the scheduler. The API is already pinned to one uvicorn
worker for chat (`app/main.py:warn_if_sharded`). Running more than one worker
requires a shared lock first, so that only the lock holder schedules.
