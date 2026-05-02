#!/usr/bin/env bash
# Z-Core Database Backup
set -euo pipefail

DB_PATH="${ZCORE_DB_PATH:-data/zcore.db}"
BACKUP_DIR="${ZCORE_BACKUP_DIR:-backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "${BACKUP_DIR}"

if [ ! -f "${DB_PATH}" ]; then
    echo "❌ Database not found: ${DB_PATH}"
    exit 1
fi

# Use SQLite backup (safe for concurrent access)
sqlite3 "${DB_PATH}" ".backup '${BACKUP_DIR}/zcore_${TIMESTAMP}.db'"

# Compress
gzip "${BACKUP_DIR}/zcore_${TIMESTAMP}.db"

# Keep last 30 backups
ls -t "${BACKUP_DIR}"/zcore_*.db.gz 2>/dev/null | tail -n +31 | xargs -r rm

echo "✅ Backup: ${BACKUP_DIR}/zcore_${TIMESTAMP}.db.gz"
