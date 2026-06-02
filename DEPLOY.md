# Deploying the bulletin generator

Mirrors the Sermon Broadcaster setup: a venv-backed **gunicorn** process managed
by **systemd**, on the homelab LAN, updated with **git pull**. No auth — it's
LAN-only.

**This deployment's choices** (the Linux VM also runs unifi-tools and
sermon-broadcaster):
- **Port 8000** (confirmed free on the VM; sermon-broadcaster/unifi-tools use
  other ports). gunicorn binds `127.0.0.1:8000`.
- The **git checkout and venv are owned by your own user** (`larryherzogjr`),
  who is GitHub-authed and sudo-capable, so `git pull` / `pip` need no sudo.
  The **service runs as the hardened `bulletin` user**, which only needs read
  access to the checkout and read-write to its data dir.
- The repo is **private**, so cloning/pulling uses your user's GitHub auth.

Replace `larryherzogjr` below with your shell username if different.

## One-time prod setup

Run on the VM as your own sudo-capable user.

```sh
# 1. System libraries WeasyPrint renders through (Linux puts them on the
#    standard loader path — no dyld shim needed, unlike macOS dev).
sudo apt update
sudo apt install -y python3-venv python3-pip \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    fonts-liberation        # metric-compatible Arial/Times for correct fit

# 2. Service user (no login; runs gunicorn only) + data dir
sudo useradd --system --shell /usr/sbin/nologin bulletin
sudo mkdir -p /var/lib/bulletin
sudo chown bulletin:bulletin /var/lib/bulletin

# 3. Clone as YOURSELF (you're GitHub-authed; the repo is private).
#    You own the checkout, so future `git pull`/`pip` need no sudo.
sudo mkdir -p /opt/bulletin-generator
sudo chown "$USER":"$USER" /opt/bulletin-generator
git clone https://github.com/larryherzogjr/bulletin-generator.git /opt/bulletin-generator
cd /opt/bulletin-generator

# 4. venv + deps (as yourself)
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt

# 5. Let the bulletin service user READ the checkout (you own it; it runs it).
#    World-readable is fine on a single-tenant homelab box; tighten if needed.
chmod -R a+rX /opt/bulletin-generator

# 6. Install + start the service
sudo cp deploy/bulletin.service /etc/systemd/system/bulletin.service
sudo systemctl daemon-reload
sudo systemctl enable --now bulletin
curl -fsS http://127.0.0.1:8000/healthz && echo OK
```

The DB lives at `/var/lib/bulletin/bulletin.sqlite3` (set via `BULLETIN_DB` in
the unit) — **outside** the git checkout, so updates never touch week data.
On first request the schema auto-creates; seed a starting week if you like
(run as the service user so the file is owned correctly):

```sh
sudo -u bulletin BULLETIN_DB=/var/lib/bulletin/bulletin.sqlite3 \
    /opt/bulletin-generator/.venv/bin/python manage.py seed
```

## The dev → prod loop

1. **Develop on macOS** (see [README.md](README.md) for the local setup —
   Homebrew libs + the dyld shim in `render.py`).
2. **Commit & push** from the dev machine.
3. **Update prod** — on the VM, **as yourself** (you own the checkout; the
   script `sudo`s only for the service restart):

   ```sh
   /opt/bulletin-generator/deploy/update.sh
   ```

   It pulls, syncs deps, restarts the service, and health-checks. On a failed
   health check it prints the last 30 journal lines and exits non-zero, so a
   bad deploy is obvious immediately.

## Reach it from other machines on the LAN

gunicorn binds `127.0.0.1:8000`, so by default it's reachable only on the VM.
To serve the LAN, either change the unit's `--bind` to `0.0.0.0:8000` and browse
to `http://<VM-IP>:8000`, or (preferred, and consistent with how you'd expose
unifi-tools / sermon-broadcaster) front it with nginx/Caddy on a hostname.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| 502 / won't start | `sudo journalctl -u bulletin -n 50 --no-pager` |
| "cannot load library 'libgobject…'" | WeasyPrint system libs (step 1) missing |
| Fonts look wrong / spacing drifts | `fonts-liberation` not installed (step 1) |
| Week data vanished after update | DB must be at `BULLETIN_DB`, not in the checkout |
| Health check fails | `curl -v http://127.0.0.1:8000/healthz` for the error |
| `update.sh`: permission denied on pull | Run it as the user who owns `/opt/bulletin-generator`, not as `bulletin` |
| Service can't read app after update | `chmod -R a+rX /opt/bulletin-generator` (new files from pull) |
| Port 8000 already in use | `sudo ss -ltnp \| grep :8000`; change `--bind` in the unit + `HEALTH_URL` in update.sh |
