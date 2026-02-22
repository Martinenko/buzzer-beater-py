#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required" >&2
  exit 1
fi

REMOTE_NAME="${RCLONE_REMOTE_NAME:-gdrive}"
REMOTE_DIR="${RCLONE_REMOTE_DIR:-bbscout-backups}"
RETENTION_COUNT="${RCLONE_RETENTION_COUNT:-7}"

# Parse DATABASE_URL using Python to avoid brittle shell parsing
read -r DB_USER DB_PASSWORD DB_HOST DB_PORT DB_NAME < <(
  python - <<'PY'
import os
from urllib.parse import urlparse

url = os.environ.get("DATABASE_URL")
if not url:
    raise SystemExit("DATABASE_URL is required")

parsed = urlparse(url)
user = parsed.username or ""
password = parsed.password or ""
host = parsed.hostname or ""
port = str(parsed.port or 3306)
name = (parsed.path or "").lstrip("/")

print(user, password, host, port, name)
PY
)

if [[ -z "$DB_HOST" || -z "$DB_NAME" ]]; then
  echo "Failed to parse DATABASE_URL" >&2
  exit 1
fi

TIMESTAMP=$(date -u +"%Y%m%d-%H%M%S")
BACKUP_NAME="bbscout-db-${TIMESTAMP}.sql.gz"
BACKUP_PATH="/tmp/${BACKUP_NAME}"

mysqldump \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --user="$DB_USER" \
  --password="$DB_PASSWORD" \
  --single-transaction \
  --routines \
  --triggers \
  --events \
  --set-gtid-purged=OFF \
  "$DB_NAME" | gzip > "$BACKUP_PATH"

rclone mkdir "${REMOTE_NAME}:${REMOTE_DIR}"
rclone copyto "$BACKUP_PATH" "${REMOTE_NAME}:${REMOTE_DIR}/${BACKUP_NAME}"

rm -f "$BACKUP_PATH"

# Retention cleanup
FILE_LIST=$(rclone lsf "${REMOTE_NAME}:${REMOTE_DIR}" --files-only | sort || true)
FILE_COUNT=$(echo "$FILE_LIST" | sed '/^$/d' | wc -l | tr -d ' ')

if [[ "$FILE_COUNT" -gt "$RETENTION_COUNT" ]]; then
  DELETE_COUNT=$((FILE_COUNT - RETENTION_COUNT))
  echo "$FILE_LIST" | sed '/^$/d' | head -n "$DELETE_COUNT" | while read -r old_file; do
    rclone deletefile "${REMOTE_NAME}:${REMOTE_DIR}/${old_file}"
  done
fi

echo "Backup completed: ${BACKUP_NAME}"