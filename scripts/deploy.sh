#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Z-Core Zero-Downtime Deploy Script
# Usage: ./scripts/deploy.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

APP_DIR="${ZCORE_APP_DIR:-/opt/zcore}"
BRANCH="${ZCORE_BRANCH:-main}"
BACKUP_DIR="${APP_DIR}/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "🚀 Z-Core Deploy — ${TIMESTAMP}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Backup database ──────────────────────────────────────
if [ -f "${APP_DIR}/data/zcore.db" ]; then
    mkdir -p "${BACKUP_DIR}"
    echo "📦 Backing up database..."
    cp "${APP_DIR}/data/zcore.db" "${BACKUP_DIR}/zcore_${TIMESTAMP}.db"
    # Keep only last 10 backups
    ls -t "${BACKUP_DIR}"/zcore_*.db 2>/dev/null | tail -n +11 | xargs -r rm
    echo "   ✅ Backup: ${BACKUP_DIR}/zcore_${TIMESTAMP}.db"
fi

# ── 2. Pull latest code ─────────────────────────────────────
echo "📥 Pulling latest code (${BRANCH})..."
cd "${APP_DIR}"
git fetch origin "${BRANCH}"
git reset --hard "origin/${BRANCH}"
echo "   ✅ Code updated: $(git rev-parse --short HEAD)"

# ── 3. Update dependencies ──────────────────────────────────
echo "📦 Updating dependencies..."
if [ -d "venv" ]; then
    source venv/bin/activate
    pip install --no-cache-dir -q -r requirements.txt
    echo "   ✅ Dependencies updated"
else
    echo "   ⚠️  No venv found, skipping pip install"
fi

# ── 4. Run migrations (if any) ──────────────────────────────
echo "🗄️  Checking migrations..."
# Future: python -m migrations.run_pending

# ── 5. Build CSS (if Tailwind CLI present) ──────────────────
if command -v tailwindcss &> /dev/null; then
    echo "🎨 Building CSS..."
    tailwindcss -i ./app/static/css/input.css -o ./app/static/css/style.css --minify
    echo "   ✅ CSS built"
fi

# ── 6. Restart application ──────────────────────────────────
echo "🔄 Restarting application..."

# Try systemd first
if systemctl is-active --quiet zcore 2>/dev/null; then
    sudo systemctl restart zcore
    echo "   ✅ Restarted via systemd"
# Try Docker
elif docker ps --format '{{.Names}}' | grep -q zcore; then
    cd docker && docker compose restart && cd ..
    echo "   ✅ Restarted via Docker"
# Try process manager (pm2, supervisor, etc.)
elif command -v pm2 &> /dev/null && pm2 list 2>/dev/null | grep -q zcore; then
    pm2 restart zcore
    echo "   ✅ Restarted via pm2"
else
    echo "   ⚠️  No process manager detected. Manual restart needed."
    echo "   Run: cd ${APP_DIR} && python -m app.main"
fi

# ── 7. Health check ─────────────────────────────────────────
echo "🏥 Health check..."
sleep 2
if curl -sf http://localhost:8000/ > /dev/null 2>&1; then
    echo "   ✅ Application is healthy"
else
    echo "   ❌ Health check failed!"
    echo "   Rolling back..."
    if [ -f "${BACKUP_DIR}/zcore_${TIMESTAMP}.db" ]; then
        cp "${BACKUP_DIR}/zcore_${TIMESTAMP}.db" "${APP_DIR}/data/zcore.db"
    fi
    git checkout HEAD~1
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Deploy complete! $(git rev-parse --short HEAD)"
