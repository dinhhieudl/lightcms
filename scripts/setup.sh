#!/usr/bin/env bash
# Z-Core First-Run Setup
set -euo pipefail

echo "⚡ Z-Core Framework Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "🐍 Creating virtual environment..."
    python3 -m venv venv
    echo "   ✅ venv created"
fi

source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install --no-cache-dir -q -r requirements.txt
echo "   ✅ Dependencies installed"

# Create .env from example
if [ ! -f ".env" ]; then
    cp .env.example .env
    # Generate secret key
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/change-me-openssl-rand-hex-32/${SECRET}/" .env
    echo "   ✅ .env created (please customize it)"
fi

# Create data directory
mkdir -p data

# Initialize database
echo "🗄️  Initializing database..."
python3 -c "from app.models.database import init_db; init_db()"
echo "   ✅ Database initialized"

# Create admin user
echo ""
echo "👤 Create admin user:"
read -p "   Username: " ADMIN_USER
read -s -p "   Password: " ADMIN_PASS
echo ""

python3 -c "
import sys; sys.path.insert(0, '.')
from app.models.database import init_db, get_session, User, UserRole
from app.core.security import hash_password
init_db()
db = get_session()
if db.query(User).filter(User.username == '${ADMIN_USER}').first():
    print('   ⚠️  User already exists')
else:
    user = User(
        username='${ADMIN_USER}',
        email='${ADMIN_USER}@localhost',
        password_hash=hash_password('${ADMIN_PASS}'),
        display_name='Admin',
        role=UserRole.ADMIN,
    )
    db.add(user)
    db.commit()
    print('   ✅ Admin user created')
db.close()
"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup complete!"
echo ""
echo "Run:  source venv/bin/activate && python -m app.main"
echo "Open: http://localhost:8000/admin"
