# Deploying the bulletin generator

Mirrors the Sermon Broadcaster setup: a venv-backed **gunicorn** process managed
by **systemd**, on the office machine / homelab LAN, updated with **git pull**.
No auth — it's LAN-only.

## One-time prod setup

Assumes a Linux box (Debian/Ubuntu-ish). Run as a sudo-capable user.

```sh
# 1. System libraries WeasyPrint renders through (Linux puts them on the
#    standard loader path — no dyld shim needed, unlike macOS dev).
sudo apt install -y python3-venv python3-pip \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    fonts-liberation        # metric-compatible Arial/Times for correct fit

# 2. Dedicated service user + app dir + data dir
sudo useradd --system --home /opt/bulletin-generator --shell /usr/sbin/nologin bulletin
sudo mkdir -p /opt/bulletin-generator /var/lib/bulletin
sudo chown bulletin:bulletin /var/lib/bulletin

# 3. Clone + venv + deps
sudo -u bulletin git clone <repo-url> /opt/bulletin-generator
cd /opt/bulletin-generator
sudo -u bulletin python3 -m venv .venv
sudo -u bulletin ./.venv/bin/python -m pip install -r requirements.txt

# 4. Install + start the service
sudo cp deploy/bulletin.service /etc/systemd/system/bulletin.service
#   (review paths/User in the unit first)
sudo systemctl daemon-reload
sudo systemctl enable --now bulletin
curl -fsS http://127.0.0.1:8000/healthz && echo OK
```

The DB lives at `/var/lib/bulletin/bulletin.sqlite3` (set via `BULLETIN_DB` in
the unit) — **outside** the git checkout, so updates never touch week data.
On first request the schema auto-creates; seed a starting week if you like:

```sh
sudo -u bulletin BULLETIN_DB=/var/lib/bulletin/bulletin.sqlite3 \
    /opt/bulletin-generator/.venv/bin/python manage.py seed
```

## The dev → prod loop

1. **Develop on macOS** (see [README.md](README.md) for the local setup —
   Homebrew libs + the dyld shim in `render.py`).
2. **Commit & push** from the dev machine.
3. **Update prod** — pull, sync deps, restart, health-check, all in one:

   ```sh
   sudo -u bulletin /opt/bulletin-generator/deploy/update.sh
   ```

   On a failed health check the script prints the last 30 journal lines and
   exits non-zero, so a bad deploy is obvious immediately.

## Optional: reach it from other office machines

gunicorn binds `127.0.0.1:8000`. To serve the LAN, either change the unit's
`--bind` to `0.0.0.0:8000`, or (preferred) front it with nginx/Caddy on port 80.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| 502 / won't start | `sudo journalctl -u bulletin -n 50 --no-pager` |
| "cannot load library 'libgobject…'" | WeasyPrint system libs (step 1) missing |
| Fonts look wrong / spacing drifts | `fonts-liberation` not installed (step 1) |
| Week data vanished after update | DB must be at `BULLETIN_DB`, not in the checkout |
| Health check fails | `curl -v http://127.0.0.1:8000/healthz` for the error |
