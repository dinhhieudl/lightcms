"""
Z-Core Configuration
====================
Environment-based config. All secrets from env vars or .env file.
"""

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = BASE_DIR / "app" / "static" / "uploads"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"

# Ensure data dirs exist
DATA_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# ── App ────────────────────────────────────────────────────────────────

APP_NAME = os.environ.get("ZCORE_APP_NAME", "Z-Core CMS")
APP_VERSION = "1.0.0"
DEBUG = os.environ.get("ZCORE_DEBUG", "false").lower() == "true"
HOST = os.environ.get("ZCORE_HOST", "0.0.0.0")
PORT = int(os.environ.get("ZCORE_PORT", "8000"))

# ── Database ───────────────────────────────────────────────────────────

DB_PATH = os.environ.get("ZCORE_DB_PATH", str(DATA_DIR / "zcore.db"))

# ── Security ───────────────────────────────────────────────────────────

SECRET_KEY = os.environ.get("ZCORE_SECRET_KEY", "change-me-in-production-use-openssl-rand-hex-32")
SESSION_MAX_AGE = int(os.environ.get("ZCORE_SESSION_MAX_AGE", "86400"))  # 24h
ADMIN_PREFIX = os.environ.get("ZCORE_ADMIN_PREFIX", "/admin")

# ── Site ───────────────────────────────────────────────────────────────

SITE_URL = os.environ.get("ZCORE_SITE_URL", "http://localhost:8000")
SITE_TITLE = os.environ.get("ZCORE_SITE_TITLE", "My Store")
SITE_DESCRIPTION = os.environ.get("ZCORE_SITE_DESCRIPTION", "")
SITE_LANGUAGE = os.environ.get("ZCORE_SITE_LANGUAGE", "vi")

# ── Uploads ────────────────────────────────────────────────────────────

MAX_UPLOAD_SIZE = int(os.environ.get("ZCORE_MAX_UPLOAD_MB", "10")) * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf", ".mp4", ".webm"}
WEBP_QUALITY = int(os.environ.get("ZCORE_WEBP_QUALITY", "85"))

# ── Telegram Notifications ─────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.environ.get("ZCORE_TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("ZCORE_TELEGRAM_CHAT_ID", "")

# ── Email (SMTP) ───────────────────────────────────────────────────────

SMTP_HOST = os.environ.get("ZCORE_SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("ZCORE_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("ZCORE_SMTP_USER", "")
SMTP_PASS = os.environ.get("ZCORE_SMTP_PASS", "")
SMTP_FROM = os.environ.get("ZCORE_SMTP_FROM", "")
SMTP_TLS = os.environ.get("ZCORE_SMTP_TLS", "true").lower() == "true"

# ── WooCommerce Migration ─────────────────────────────────────────────

WP_MYSQL_HOST = os.environ.get("WP_MYSQL_HOST", "localhost")
WP_MYSQL_PORT = int(os.environ.get("WP_MYSQL_PORT", "3306"))
WP_MYSQL_DB = os.environ.get("WP_MYSQL_DB", "wordpress")
WP_MYSQL_USER = os.environ.get("WP_MYSQL_USER", "root")
WP_MYSQL_PASS = os.environ.get("WP_MYSQL_PASS", "")
WP_TABLE_PREFIX = os.environ.get("WP_TABLE_PREFIX", "wp_")
WP_UPLOADS_URL = os.environ.get("WP_UPLOADS_URL", "")  # Base URL for wp-content/uploads
