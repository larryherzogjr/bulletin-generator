# Deploying the bulletin generator

Production runs Gunicorn under systemd on a Linux VM. The existing bulletin
service listens at `0.0.0.0:8000` for direct use on the trusted homelab LAN.
The ESV integration runs inside this same process and adds no listening port.
The application itself intentionally has no user accounts.

The checkout and virtual environment are owned by the sudo-capable deployment
user. The service runs as the unprivileged `bulletin` user and can write only
to `/var/lib/bulletin`.

## One-time setup

Run these commands as the deployment user:

```sh
sudo apt update
sudo apt install -y python3-venv python3-pip cron \
    nodejs npm \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    fonts-liberation poppler-utils

sudo useradd --system --shell /usr/sbin/nologin bulletin
sudo mkdir -p /var/lib/bulletin
sudo chown bulletin:bulletin /var/lib/bulletin

sudo mkdir -p /opt/bulletin-generator
sudo chown "$USER":"$USER" /opt/bulletin-generator
git clone https://github.com/larryherzogjr/bulletin-generator.git \
    /opt/bulletin-generator
cd /opt/bulletin-generator

python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements-dev.txt
npm ci --omit=dev --ignore-scripts --no-audit --no-fund
./.venv/bin/python -m pytest -q

sudo chgrp -R bulletin /opt/bulletin-generator
sudo chmod -R g+rX,o-rwx /opt/bulletin-generator
sudo find /opt/bulletin-generator -type d -exec chmod g+s {} +
sudo cp deploy/bulletin.service /etc/systemd/system/bulletin.service
sudo install -m 0644 deploy/bulletin-cleanup.cron \
    /etc/cron.d/bulletin-cleanup
sudo systemctl daemon-reload
sudo systemctl enable --now cron
sudo systemctl enable --now bulletin
curl -fsS http://127.0.0.1:8000/healthz && echo OK
```

## Automatic ESV Scripture

Register the church's noncommercial application at
[api.esv.org](https://api.esv.org/), then place the key in the root-owned
environment file referenced by the systemd unit. Do not commit the key:

```sh
sudo install -m 600 -o root -g root /dev/null /etc/bulletin-generator.env
sudoedit /etc/bulletin-generator.env
```

Add exactly this setting, using the key issued by Crossway:

```text
ESV_API_KEY=your-key-from-Crossway
```

Then restart the service:

```sh
sudo systemctl daemon-reload
sudo systemctl restart bulletin
```

The application stores only the Scripture references and source selection for
automatic ESV weeks. Passage text is fetched transiently for editor previews
and generated files, and is not retained in SQLite.

The version constraints validated by CI are applied automatically through
`requirements-dev.txt`. Do not install unconstrained dependencies in the
production virtual environment.

## Database and initial data

`BULLETIN_DB` points to `/var/lib/bulletin/bulletin.sqlite3`, outside the Git
checkout. Initialize or seed it as the service user:

```sh
sudo -u bulletin BULLETIN_DB=/var/lib/bulletin/bulletin.sqlite3 \
    /opt/bulletin-generator/.venv/bin/python \
    /opt/bulletin-generator/manage.py init

sudo -u bulletin BULLETIN_DB=/var/lib/bulletin/bulletin.sqlite3 \
    /opt/bulletin-generator/.venv/bin/python \
    /opt/bulletin-generator/manage.py seed
```

The seed content is fictional and exists only to demonstrate layout.

## Normal update workflow

After committing and pushing a tested change, run:

```sh
/opt/bulletin-generator/deploy/update.sh
```

The updater refuses tracked local production changes, then:

1. records the currently deployed revision and fast-forwards Git;
2. installs the pinned Python and PowerPoint runtime dependencies;
3. creates an online timestamped SQLite backup;
4. runs pytest and database/schema/PDF/PowerPoint render preflight checks;
5. installs the current systemd unit and restarts the service;
6. verifies `/healthz`.

Any failure after the pull resets the clean checkout to the previous revision,
restores its dependencies and unit file, restarts it, and checks rollback
health. The database backup is retained.

Environment overrides supported by the updater are `APP_DIR`, `SERVICE`,
`SERVICE_USER`, `SERVICE_GROUP`, `BULLETIN_DB`, `HEALTH_URL`, `UNIT_DEST`, and
`CRON_DEST`.

## Old-week cleanup

The updater installs `/etc/cron.d/bulletin-cleanup`. Every day at 3:17 AM it
runs `manage.py purge --months 13` as the unprivileged `bulletin` user against
the production database. Cleanup compares the date entered in the week's
Weekly information (for example, `May 31, 2026`) with a 13-calendar-month
cutoff. It deletes only dates strictly older than that cutoff.

Weeks with **Keep** checked are never deleted. Weeks with a blank or
unrecognized date are also retained so a typo cannot destroy data. Manual
deletion enforces the same Keep flag on the server, in addition to disabling
the button in the browser.

Test the cleanup command manually at any time:

```sh
sudo -u bulletin BULLETIN_DB=/var/lib/bulletin/bulletin.sqlite3 \
    /opt/bulletin-generator/.venv/bin/python \
    /opt/bulletin-generator/manage.py purge --months 13
```

## Backups and recovery

Automatic backups are written under `/var/lib/bulletin/backups/`. Monitor that
directory and copy backups to a different machine or storage volume; an onsite
backup alone does not protect against VM/disk loss.

Create an extra backup at any time:

```sh
sudo -u bulletin BULLETIN_DB=/var/lib/bulletin/bulletin.sqlite3 \
    /opt/bulletin-generator/.venv/bin/python \
    /opt/bulletin-generator/manage.py backup
```

Verify the live database and render path:

```sh
sudo -u bulletin BULLETIN_DB=/var/lib/bulletin/bulletin.sqlite3 \
    /opt/bulletin-generator/.venv/bin/python \
    /opt/bulletin-generator/manage.py check --render
```

To restore, stop the service, preserve the failed database separately, copy a
chosen backup to `/var/lib/bulletin/bulletin.sqlite3`, restore ownership to
`bulletin:bulletin`, and start the service. Run `manage.py check --render`
before reopening access.

## Network boundary

Port 8000 is intended only for the trusted LAN/VPN. Restrict it at the host and
network firewalls and do not forward it from the public internet. If the app is
later placed behind nginx or Caddy, change Gunicorn to a loopback bind and have
the proxy provide HTTPS and authentication, preserve the original `Host`
header, and avoid caching edit or PDF responses containing parish data.

The app rejects browser requests marked cross-site and POST requests whose
Origin/Referer host differs from the requested host. The default JSON request
limit is 1 MiB (`BULLETIN_MAX_CONTENT_LENGTH=1048576`).

## Troubleshooting

| Symptom | Check |
|---|---|
| Service will not start | `sudo journalctl -u bulletin -n 50 --no-pager` |
| Native-library error | Confirm the Pango/Cairo packages above are installed |
| Font/layout drift | `fc-list \| grep -i liberation` |
| PDF returns HTTP 422 | Shorten the section named in the layout error |
| PowerPoint returns HTTP 422 | Complete the missing creed, lesson, sermon, hymn, or baptism field named on the error page |
| Update refuses to run | `git status`; production tracked files must be clean |
| Preflight fails | Run pytest and `manage.py check --render` manually |
| Rollback also fails | Inspect the journal and verify DB ownership/path |
| Port conflict | `sudo ss -ltnp \| grep :8000` |
