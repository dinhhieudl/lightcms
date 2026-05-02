"""
Admin Authentication Middleware
===============================
Cookie-based session auth for the admin panel.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse
from app.core.security import get_user_from_session
from app.models.database import get_session
from config import settings


class AdminAuthMiddleware(BaseHTTPMiddleware):
    """Protects admin routes with cookie-based session authentication."""

    # Paths that don't require auth
    PUBLIC_PATHS = {
        f"{settings.ADMIN_PREFIX}/login",
        f"{settings.ADMIN_PREFIX}/login/",
    }

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Only intercept admin routes
        if not path.startswith(settings.ADMIN_PREFIX):
            return await call_next(request)

        # Allow login page
        if path.rstrip("/") in {p.rstrip("/") for p in self.PUBLIC_PATHS}:
            return await call_next(request)

        # Check session cookie
        session_key = request.cookies.get("zcore_session")
        if session_key:
            db = get_session()
            try:
                user = get_user_from_session(db, session_key)
                if user:
                    request.state.user = user
                    return await call_next(request)
            finally:
                db.close()

        # Not authenticated → redirect to login
        return RedirectResponse(
            url=f"{settings.ADMIN_PREFIX}/login?next={path}",
            status_code=302
        )
