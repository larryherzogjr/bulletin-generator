#!/usr/bin/env bash
# Prod update loop for the bulletin generator (run on the prod box).
# Mirrors the Sermon Broadcaster pattern: pull, sync deps, restart, health-check.
#
# Run as YOUR OWN user (the one that owns the checkout and is authed to GitHub
# and sudo-capable) — NOT as the `bulletin` service user:
#
#   /opt/bulletin-generator/deploy/update.sh
#
# Idempotent and safe to re-run. The SQLite DB lives outside this checkout
# (BULLETIN_DB in the service unit), so a pull never touches week data.

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/bulletin-generator}"
SERVICE="${SERVICE:-bulletin}"
SERVICE_USER="${SERVICE_USER:-bulletin}"
SERVICE_GROUP="${SERVICE_GROUP:-bulletin}"
DB_PATH="${BULLETIN_DB:-/var/lib/bulletin/bulletin.sqlite3}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/healthz}"
UNIT_DEST="${UNIT_DEST:-/etc/systemd/system/${SERVICE}.service}"
CRON_DEST="${CRON_DEST:-/etc/cron.d/${SERVICE}-cleanup}"
ENV_FILE="${ENV_FILE:-/etc/bulletin-generator.env}"

cd "$APP_DIR"

secure_checkout() {
  sudo chgrp -R "$SERVICE_GROUP" "$APP_DIR"
  sudo chmod -R g+rX,o-rwx "$APP_DIR"
  sudo find "$APP_DIR" -type d -exec chmod g+s {} +
}

wait_for_health() {
  local attempt
  for attempt in {1..10}; do
    if curl --connect-timeout 2 --max-time 3 -fsS "$HEALTH_URL" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "tracked production files have local changes; refusing to update" >&2
  exit 1
fi

PREVIOUS_REV="$(git rev-parse HEAD)"
UPDATED=0

rollback() {
  local failed_rc="$1"
  trap - ERR
  set +e
  if [[ "$UPDATED" -eq 1 ]]; then
    echo "==> update failed; rolling back to $PREVIOUS_REV" >&2
    git reset --hard "$PREVIOUS_REV"
    if [[ -f constraints.txt ]]; then
      ./.venv/bin/python -m pip install -q -c constraints.txt -r requirements.txt
    else
      ./.venv/bin/python -m pip install -q -r requirements.txt
    fi
    if [[ -f package-lock.json ]]; then
      npm ci --omit=dev --ignore-scripts --no-audit --no-fund
    fi
    secure_checkout
    sudo cp "$APP_DIR/deploy/bulletin.service" "$UNIT_DEST"
    sudo systemctl daemon-reload
    sudo systemctl restart "$SERVICE"
    if wait_for_health; then
      echo "==> rollback healthy" >&2
    else
      echo "==> rollback health check also failed" >&2
      sudo journalctl -u "$SERVICE" -n 30 --no-pager >&2
    fi
  fi
  exit "$failed_rc"
}

trap 'rollback $?' ERR

echo "==> git pull"
git pull --ff-only
UPDATED=1

echo "==> sync pinned dependencies"
./.venv/bin/python -m pip install -q -r requirements-dev.txt
npm ci --omit=dev --ignore-scripts --no-audit --no-fund

# New files from the pull are owned by this (admin) user; ensure the
# unprivileged service user can still read them.
echo "==> ensure service user can read the checkout"
secure_checkout

echo "==> back up database"
sudo -u "$SERVICE_USER" env BULLETIN_DB="$DB_PATH" \
  "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" backup

echo "==> test application"
./.venv/bin/python -m pytest -q
# Let systemd read the same root-owned environment file as the app. Running
# sudo -u alone drops ESV_API_KEY and cannot read that file as the service user.
# The key never needs to appear in shell arguments or deployment output.
sudo systemd-run --quiet --wait --pipe --collect \
  --property="User=$SERVICE_USER" \
  --property="Group=$SERVICE_GROUP" \
  --property="WorkingDirectory=$APP_DIR" \
  --property="EnvironmentFile=-$ENV_FILE" \
  --setenv="BULLETIN_DB=$DB_PATH" \
  "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" check --render

echo "==> install service unit"
sudo cp "$APP_DIR/deploy/bulletin.service" "$UNIT_DEST"
sudo systemctl daemon-reload

echo "==> restart service ($SERVICE)"
sudo systemctl restart "$SERVICE"

echo "==> health check ($HEALTH_URL)"
if wait_for_health; then
  echo "    ok"
  echo "==> install daily old-week cleanup"
  sudo install -m 0644 "$APP_DIR/deploy/bulletin-cleanup.cron" "$CRON_DEST"
  echo "==> done"
  trap - ERR
  exit 0
fi

echo "    health check FAILED — recent logs:" >&2
sudo journalctl -u "$SERVICE" -n 30 --no-pager >&2
false
