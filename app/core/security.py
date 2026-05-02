"""
Z-Core Security
===============
Password hashing, session management, CSRF protection.
"""

import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timezone, timedelta
from functools import wraps

from config import settings


def hash_password(password: str) -> str:
    """Hash password with SHA-256 + salt (bcrypt is overkill for SQLite admin)."""
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}${h}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash."""
    try:
        salt, h = stored_hash.split("$", 1)
        return hmac.compare_digest(
            hashlib.sha256(f"{salt}{password}".encode()).hexdigest(),
            h
        )
    except (ValueError, AttributeError):
        return False


def generate_session_key() -> str:
    """Generate a cryptographically secure session key."""
    return secrets.token_urlsafe(48)


def generate_csrf_token() -> str:
    """Generate CSRF token for forms."""
    return secrets.token_hex(32)


def verify_csrf_token(token: str, stored_token: str) -> bool:
    """Constant-time CSRF token comparison."""
    if not token or not stored_token:
        return False
    return hmac.compare_digest(token, stored_token)


def create_session(db, user_id: int) -> str:
    """Create a new admin session, return session key."""
    from app.models.database import Session as SessionModel

    # Clean expired sessions
    db.query(SessionModel).filter(
        SessionModel.expires_at < datetime.now(timezone.utc)
    ).delete()

    key = generate_session_key()
    expires = datetime.now(timezone.utc) + timedelta(seconds=settings.SESSION_MAX_AGE)
    session = SessionModel(
        session_key=key,
        user_id=user_id,
        expires_at=expires,
    )
    db.add(session)
    db.commit()
    return key


def get_user_from_session(db, session_key: str):
    """Retrieve user from session key. Returns None if invalid/expired."""
    from app.models.database import Session as SessionModel, User

    if not session_key:
        return None

    session = db.query(SessionModel).filter(
        SessionModel.session_key == session_key,
        SessionModel.expires_at > datetime.now(timezone.utc)
    ).first()

    if not session:
        return None

    return db.query(User).filter(User.id == session.user_id, User.is_active == True).first()


def destroy_session(db, session_key: str):
    """Destroy a session (logout)."""
    from app.models.database import Session as SessionModel
    db.query(SessionModel).filter(SessionModel.session_key == session_key).delete()
    db.commit()
