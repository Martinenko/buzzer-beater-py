#!/usr/bin/env bash
set -euo pipefail

RCLONE_CONFIG_DIR="/root/.config/rclone"
RCLONE_CONFIG_PATH="${RCLONE_CONFIG_DIR}/rclone.conf"

if [[ -n "${RCLONE_CONFIG_B64:-}" ]]; then
  mkdir -p "$RCLONE_CONFIG_DIR"
  umask 077
  echo "$RCLONE_CONFIG_B64" | base64 -d > "$RCLONE_CONFIG_PATH"
elif [[ -n "${RCLONE_CONFIG:-}" ]]; then
  mkdir -p "$RCLONE_CONFIG_DIR"
  umask 077
  echo "$RCLONE_CONFIG" > "$RCLONE_CONFIG_PATH"
fi

CRON_SCHEDULE="${BACKUP_CRON_SCHEDULE:-0 3 * * *}"
CRON_FILE="/app/scripts/backup.cron"

echo "${CRON_SCHEDULE} /app/scripts/backup_to_gdrive.sh" > "$CRON_FILE"

echo "Starting backup scheduler..."
supercronic "$CRON_FILE" &

alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"