#!/usr/bin/env bash
# Prod update loop for the bulletin generator (run on the prod box).
# Mirrors the Sermon Broadcaster pattern: pull, sync deps, restart, health-check.
#
#   sudo -u bulletin /opt/bulletin-generator/deploy/update.sh
#
# Idempotent and safe to re-run. The SQLite DB lives outside this checkout
# (BULLETIN_DB in the service unit), so a pull never touches week data.

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/bulletin-generator}"
SERVICE="${SERVICE:-bulletin}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/healthz}"

cd "$APP_DIR"

echo "==> git pull"
git pull --ff-only

echo "==> sync dependencies"
./.venv/bin/python -m pip install -q -r requirements.txt

echo "==> restart service ($SERVICE)"
sudo systemctl restart "$SERVICE"

echo "==> health check ($HEALTH_URL)"
for i in $(seq 1 10); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "    ok"
    echo "==> done"
    exit 0
  fi
  sleep 1
done

echo "    health check FAILED — recent logs:" >&2
sudo journalctl -u "$SERVICE" -n 30 --no-pager >&2
exit 1
