# Deploying `daily_album_selector` as a systemd Service

This guide covers setting up the cron-driven daily album selection as a systemd timer on a Linux production host.

## Prerequisites

- The `spinshare` repo is checked out and the backend virtualenv is built at `backend/.venv`.
- A `.env` file exists at `backend/.env` with `DATABASE_URL` and `SECRET_KEY` set.
- You have sudo access on the target host.

## Files to create

### 1. `/etc/systemd/system/spinshare-daily-select.service`

```ini
[Unit]
Description=SpinShare daily album selector
After=network.target postgresql.service

[Service]
Type=oneshot
User=spinshare
WorkingDirectory=/opt/spinshare/backend
ExecStart=/opt/spinshare/backend/.venv/bin/python scripts/daily_album_selector.py
EnvironmentFile=/opt/spinshare/backend/.env
StandardOutput=journal
StandardError=journal
SyslogIdentifier=spinshare-daily-select
```

### 2. `/etc/systemd/system/spinshare-daily-select.timer`

```ini
[Unit]
Description=Run SpinShare daily album selector at midnight UTC

[Timer]
OnCalendar=*-*-* 00:00:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
```

`Persistent=true` ensures the job catches up on the next boot if the host was down at midnight.

## Installation

```bash
# Copy unit files
sudo cp spinshare-daily-select.service /etc/systemd/system/
sudo cp spinshare-daily-select.timer   /etc/systemd/system/

# Reload systemd and enable the timer
sudo systemctl daemon-reload
sudo systemctl enable --now spinshare-daily-select.timer

# Verify the timer is scheduled
sudo systemctl list-timers spinshare-daily-select.timer
```

## Manual test run

Trigger the service directly without waiting for midnight:

```bash
sudo systemctl start spinshare-daily-select.service
sudo journalctl -u spinshare-daily-select.service -n 50
```

Because `select_daily_albums` is idempotent (it returns the existing selection if albums were already chosen today), running this manually during the day is safe and will not add duplicate selections.

## Checking logs

```bash
# Last run output
sudo journalctl -u spinshare-daily-select.service -n 100

# Follow live
sudo journalctl -u spinshare-daily-select.service -f

# Timer status (shows next scheduled run)
sudo systemctl status spinshare-daily-select.timer
```

## Adjusting the schedule

Edit the `OnCalendar` line in the `.timer` file, then reload:

```bash
sudo systemctl daemon-reload
sudo systemctl restart spinshare-daily-select.timer
```

`systemd-analyze calendar '*-*-* 00:00:00 UTC'` can be used to validate calendar expressions before applying them.
