#!/usr/bin/env bash
# Run after deploying the app's /bulletin mount: sudo bash deploy/install-nginx.sh
set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
    echo "Run this installer with sudo." >&2
    exit 1
fi
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
site=/etc/nginx/sites-available/home.grace
snippet=/etc/nginx/snippets/bulletin-generator.conf

# Fail before changing nginx if the app has not yet been updated.
curl --fail --silent --show-error --max-time 10 \
    http://127.0.0.1:8000/bulletin/healthz >/dev/null
nginx -t

backup_dir="$(mktemp -d /etc/nginx/bulletin-backup.XXXXXX)"
cp -p "$site" "$backup_dir/home.grace"
if [[ -e "$snippet" ]]; then
    cp -p "$snippet" "$backup_dir/bulletin-generator.conf"
fi

rollback() {
    local status="$?"
    trap - ERR
    cp -p "$backup_dir/home.grace" "$site"
    if [[ -e "$backup_dir/bulletin-generator.conf" ]]; then
        cp -p "$backup_dir/bulletin-generator.conf" "$snippet"
    else
        rm -f "$snippet"
    fi
    nginx -t && systemctl reload nginx
    echo "nginx installation failed; restored configuration from $backup_dir" >&2
    exit "$status"
}
trap rollback ERR

install -m 0644 "$project_dir/deploy/nginx-home.grace.conf" "$snippet"
python3 - "$site" <<'PY'
from pathlib import Path
import sys

site = Path(sys.argv[1])
text = site.read_text()
include = "    include /etc/nginx/snippets/bulletin-generator.conf;"
anchor = "    include /etc/nginx/snippets/fellowship-announcements.conf;"
if include.strip() not in text:
    if text.count(anchor) != 1:
        raise SystemExit("Expected exactly one announcements include; inspect home.grace manually.")
    site.write_text(text.replace(anchor, anchor + "\n\n" + include))
PY
nginx -t
systemctl reload nginx
curl --fail --silent --show-error --max-time 10 \
    --cacert /var/www/grace-free/grace-free-root-ca.crt \
    --resolve home.grace:443:127.0.0.1 https://home.grace/bulletin/healthz
curl --fail --silent --show-error --max-time 10 http://127.0.0.1:8000/healthz
trap - ERR
echo ""
echo "Installed https://home.grace/bulletin/; port 8000 remains available."
echo "Previous nginx configuration: $backup_dir"
