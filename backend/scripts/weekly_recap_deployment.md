# Deploying `weekly_recap_generator` as a systemd Service

This guide sets up the weekly recap generation as a systemd timer on a Linux
production host. It mirrors `daily_album_selector_deployment.md`.

## Prerequisites

- The `spinshare` repo is checked out and the backend virtualenv is built at `backend/.venv`.
- A `.env` file exists at `backend/.env` with `DATABASE_URL` and `SECRET_KEY` set.
- The `group_recaps` and `recap_views` tables exist (run `alembic upgrade head`).
- You have sudo access on the target host.

## Files to create

### 1. `/etc/systemd/system/spinshare-weekly-recap.service`

```ini
[Unit]
Description=SpinShare weekly recap generator
After=network.target postgresql.service

[Service]
Type=oneshot
User=spinshare
WorkingDirectory=/opt/spinshare/backend
ExecStart=/opt/spinshare/backend/.venv/bin/python scripts/weekly_recap_generator.py
EnvironmentFile=/opt/spinshare/backend/.env
StandardOutput=journal
StandardError=journal
SyslogIdentifier=spinshare-weekly-recap
```

### 2. `/etc/systemd/system/spinshare-weekly-recap.timer`

```ini
[Unit]
Description=Run SpinShare weekly recap generator hourly

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
```

`Persistent=true` ensures the job catches up on the next boot if the host was down.

The generator is idempotent — each group gets at most one recap per week (a unique
constraint on `(group_id, week_start)` enforces this). Running hourly ensures that
each group-timezone Monday midnight is caught, so every group's completed week is
snapshotted promptly regardless of timezone.

## Installation

```bash
sudo cp spinshare-weekly-recap.service /etc/systemd/system/
sudo cp spinshare-weekly-recap.timer   /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now spinshare-weekly-recap.timer

sudo systemctl list-timers spinshare-weekly-recap.timer
```

## Manual / backfill run

```bash
# Generate whatever week is now due for every group (safe to run anytime — idempotent):
sudo systemctl start spinshare-weekly-recap.service

# Backfill a specific past week for one group (Monday date, group timezone):
.venv/bin/python scripts/weekly_recap_generator.py --group 42 --week-start 2026-07-27

# Force a regenerate (dev/test only — deletes and recomputes the snapshot):
.venv/bin/python scripts/weekly_recap_generator.py --group 42 --week-start 2026-07-27 --force
```

## Checking logs

```bash
sudo journalctl -u spinshare-weekly-recap.service -n 100
sudo journalctl -u spinshare-weekly-recap.service -f
sudo systemctl status spinshare-weekly-recap.timer
```
