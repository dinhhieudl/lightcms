#!/usr/bin/env python3
"""Create admin user for Z-Core."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.database import init_db, get_session, User, UserRole
from app.core.security import hash_password


def main():
    import getpass

    print("👤 Create Admin User")
    print("━" * 30)

    username = input("Username: ").strip()
    if not username:
        print("❌ Username required")
        return

    email = input("Email: ").strip() or f"{username}@localhost"
    password = getpass.getpass("Password: ")
    if not password:
        print("❌ Password required")
        return

    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("❌ Passwords don't match")
        return

    init_db()
    db = get_session()

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        print(f"⚠️  User '{username}' already exists. Updating password...")
        existing.password_hash = hash_password(password)
        db.commit()
        print("✅ Password updated")
    else:
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            display_name=username,
            role=UserRole.ADMIN,
        )
        db.add(user)
        db.commit()
        print(f"✅ Admin user '{username}' created")

    db.close()


if __name__ == "__main__":
    main()
