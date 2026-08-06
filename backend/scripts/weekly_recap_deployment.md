# Deploying `weekly_recap_generator`

This guide sets up the weekly recap generation on a Linux production host. Two
options are documented:

- **systemd timer, hourly (recommended, mirrors `daily_album_selector`)** — most
  robust: idempotent, self-healing across host downtime and every group timezone.
- **weekly crontab (simplest)** — a single Monday run; fine for a timezone-homogeneous
  deployment. See "Alternative: weekly crontab" below.

`generate_due` always snapshots the *most recently completed* Mon–Sun week for each
group (in that group's timezone), so the recap is correct no matter when the job runs —
the only difference between the two options is scheduling robustness.

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

## Alternative: weekly crontab

If you'd rather run it once a week instead of hourly, a plain crontab works. Because
the generator is idempotent and always targets the just-completed week, a single Monday
run produces the same result:

```cron
# Mondays at 06:00 US Eastern — generate the recap for the week that just ended.
CRON_TZ=America/New_York
0 6 * * 1 cd /opt/spinshare/backend && .venv/bin/python scripts/weekly_recap_generator.py >> /var/log/spinshare-weekly-recap.log 2>&1
```

Trade-offs vs. the hourly systemd timer:

- **No automatic catch-up.** If the host is down at 06:00 Monday, that week's recap is
  skipped until you run it manually (systemd's `Persistent=true` would have caught up).
- **Timezone assumption.** A single fixed run must fire *after* every group's local Monday
  has begun. 06:00 Eastern is safe for North American and European groups; only groups in
  far-western Pacific zones (≈ UTC−11 or west) could see their recap generated a day late.
  If your groups span such timezones, prefer the hourly timer (or move the run later, e.g.
  12:00 UTC).

For a timezone-homogeneous (e.g. US-centric) deployment, the weekly crontab is perfectly
adequate and the simplest thing to operate.

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
