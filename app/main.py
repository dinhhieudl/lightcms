"""
Z-Core Application Entry Point
===============================
FastAPI app with Jinja2 SSR, admin panel, and frontend routing.
"""

import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, Response
from starlette.middleware.sessions import SessionMiddleware

from config import settings
from app.models.database import init_db
from app.middleware.admin_auth import AdminAuthMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.core.templates import get_template_env

# ── Logging ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("zcore")

# ── App ────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url=None,
)

# Middleware
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AdminAuthMiddleware)

# Static files
app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")

# Template env (shared)
templates = get_template_env()

# ── Startup ────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting...")
    init_db()
    logger.info(f"📂 Database: {settings.DB_PATH}")
    logger.info(f"🌐 Site: {settings.SITE_URL}")
    logger.info(f"🔧 Admin: {settings.ADMIN_PREFIX}")

# ── Register Routes ────────────────────────────────────────────────────

from app.routes.admin import router as admin_router
from app.routes.frontend import router as frontend_router
from app.routes.api import router as api_router

app.include_router(admin_router, prefix=settings.ADMIN_PREFIX)
app.include_router(api_router, prefix="/api")
app.include_router(frontend_router)  # Catch-all last

# SEO endpoints are in frontend router (before catch-all)

# ── Run ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
