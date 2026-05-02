# Z-Core Development Guide

## Quick Start (5 minutes)

```bash
# Clone
git clone https://github.com/dinhhieudl/lightcms.git
cd lightcms

# Setup (creates venv, .env, DB, admin user)
chmod +x scripts/*.sh
./scripts/setup.sh

# Run
python3 -m app.main
# → http://localhost:8000
# → http://localhost:8000/admin (admin/admin123)
```

## Project Structure

```
lightcms/
│
├── app/                          # Application code
│   ├── __init__.py
│   ├── main.py                   # FastAPI app, middleware, startup
│   │
│   ├── core/                     # Framework core
│   │   ├── security.py           # Password hashing, sessions, CSRF
│   │   └── templates.py          # Jinja2 env, custom filters
│   │
│   ├── models/
│   │   └── database.py           # SQLAlchemy models (17 tables)
│   │
│   ├── routes/                   # URL routing
│   │   ├── admin.py              # Admin panel CRUD (20+ endpoints)
│   │   ├── frontend.py           # Public pages (15+ endpoints)
│   │   └── api.py                # JSON API (3 endpoints)
│   │
│   ├── services/
│   │   └── notification.py       # Telegram + Email notifications
│   │
│   ├── middleware/
│   │   ├── admin_auth.py         # Cookie-based admin auth
│   │   └── security_headers.py   # Security HTTP headers
│   │
│   ├── utils/
│   │   ├── image.py              # WebP conversion, thumbnails
│   │   └── seo.py                # Sitemap, robots.txt, meta tags
│   │
│   ├── templates/                # Jinja2 templates
│   │   ├── layouts/              # Base layouts (admin, frontend)
│   │   ├── components/           # Header, footer
│   │   ├── front/                # Public pages (11 templates)
│   │   └── admin/                # Admin pages (12 templates)
│   │
│   └── static/
│       ├── css/                  # Tailwind CSS
│       ├── js/                   # Minimal vanilla JS
│       └── uploads/              # User uploads (gitignored)
│
├── config/
│   ├── settings.py               # Environment-based config
│   └── nginx.conf                # Nginx reverse proxy template
│
├── migrations/
│   └── wp_migrate.py             # WordPress migration engine
│
├── scripts/
│   ├── setup.sh                  # First-run setup
│   ├── deploy.sh                 # Zero-downtime deploy
│   ├── backup.sh                 # DB backup
│   ├── build_css.sh              # Tailwind CSS build
│   ├── seed.py                   # Generate test data (1000 products)
│   ├── audit.py                  # Comprehensive audit suite
│   └── create_admin.py           # Create/reset admin user
│
├── docker/
│   ├── Dockerfile                # Multi-stage build
│   └── docker-compose.yml        # Production compose
│
├── docs/                         # Documentation
│   ├── architecture.md           # This file
│   ├── development.md            # Dev guide
│   ├── migration.md              # WordPress migration guide
│   └── fastpanel-deploy.md       # FastPanel deployment
│
├── .env.example                  # Config template
├── .gitignore
├── requirements.txt              # Python dependencies
├── tailwind.config.js            # Tailwind config
└── README.md
```

## Environment Variables

All config is in `.env` (copy from `.env.example`):

```bash
# App
ZCORE_APP_NAME=My Store           # Display name
ZCORE_DEBUG=false                  # Debug mode (auto-reload, docs)
ZCORE_HOST=0.0.0.0                # Bind address
ZCORE_PORT=8000                   # Bind port
ZCORE_SECRET_KEY=<random-64-hex>  # Session encryption key

# Site
ZCORE_SITE_URL=https://your-domain.com
ZCORE_SITE_TITLE=My Store
ZCORE_SITE_DESCRIPTION=Description for SEO
ZCORE_SITE_LANGUAGE=vi            # Template language

# Database
ZCORE_DB_PATH=data/zcore.db       # SQLite file path

# Telegram (optional)
ZCORE_TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
ZCORE_TELEGRAM_CHAT_ID=-100123456789

# Email SMTP (optional)
ZCORE_SMTP_HOST=smtp.gmail.com
ZCORE_SMTP_PORT=587
ZCORE_SMTP_USER=you@gmail.com
ZCORE_SMTP_PASS=app-password
ZCORE_SMTP_FROM=you@gmail.com

# Uploads
ZCORE_MAX_UPLOAD_MB=10            # Max file upload size
ZCORE_WEBP_QUALITY=85             # WebP compression quality
```

## Database

### Models (SQLAlchemy)

All models are in `app/models/database.py`. Key models:

```python
# Users
class User:
    id, username, email, password_hash, display_name, role, ...

# Posts (blog articles)
class Post:
    id, title, slug, content (Markdown), excerpt, featured_image,
    status (draft/published/pending/trash), author_id,
    meta_title, meta_description, canonical_url, og_image,
    published_at, view_count, is_sticky

# Pages (static content)
class Page:
    id, title, slug, content (Markdown), template, parent_id,
    status, is_homepage, meta_title, meta_description

# Products (e-commerce)
class Product:
    id, name, slug, sku, description, short_description,
    price, sale_price, cost_price, currency,
    stock_quantity, stock_status, manage_stock,
    weight, length, width, height,
    product_type (simple/variable/digital),
    is_featured, featured_image, gallery_images (JSON),
    status, meta_title, meta_description,
    view_count, sales_count, rating_avg, rating_count

# Product Variants (for variable products)
class ProductVariant:
    id, product_id, sku, name, price, sale_price,
    stock_quantity, stock_status, image_url, is_active

# Product Attributes (Color, Size, etc.)
class ProductAttribute:
    id, product_id, name, values (JSON array), is_variation

# Orders
class Order:
    id, order_number, customer_id, status,
    customer_name, customer_email, customer_phone,
    shipping_address, shipping_city, shipping_district, shipping_ward,
    subtotal, shipping_fee, discount, total,
    payment_method, payment_status, transaction_id,
    tracking_number, shipping_provider,
    admin_note, customer_note,
    telegram_notified, email_notified

# Order Items (snapshot at order time)
class OrderItem:
    id, order_id, product_id, variant_id,
    product_name, product_sku, variant_name,
    price, quantity, subtotal
```

### Direct Database Access

```python
from app.models.database import get_session, Product

db = get_session()
try:
    products = db.query(Product).filter(Product.price > 1000000).all()
    for p in products:
        print(f"{p.name}: {p.price:,.0f}₫")
finally:
    db.close()
```

### Adding New Models

1. Add model class to `app/models/database.py`
2. Import in the file that uses it
3. Run `python3 -c "from app.models.database import init_db; init_db()"`
   to create the new table (SQLite ALTER TABLE is limited, so for complex
   changes, recreate the database)

## Templates

### Creating a New Template

1. Create file in `app/templates/front/` or `app/templates/admin/`
2. Extend base layout: `{% extends "layouts/base.html" %}`
3. Use blocks: `{% block body %}...{% endblock %}`

Example:
```html
{% extends "layouts/base.html" %}

{% block body %}
{% include "components/header.html" %}

<main class="max-w-4xl mx-auto px-4 py-8">
    <h1 class="text-3xl font-bold">{{ page_title }}</h1>
    <p>{{ content }}</p>
</main>

{% include "components/footer.html" %}
{% endblock %}
```

### Available Filters

```html
{{ price|format_price }}          {# 150.000₫ #}
{{ date|timeago }}                {# 3 giờ trước #}
{{ text|truncate_html(160) }}     {# Stripped, truncated #}
{{ md_content|markdown|safe }}    {# Markdown → HTML #}
{{ data|tojson }}                 {# JSON serialize #}
{{ name|slugify }}                {# URL-safe slug #}
```

### Adding Custom Filters

In `app/core/templates.py`, add to `get_template_env()`:

```python
env.filters["my_filter"] = my_function
```

## Routes

### Adding a New Public Route

In `app/routes/frontend.py`:

```python
@router.get("/my-page", response_class=HTMLResponse)
async def my_page(request: Request, db: DBSession = Depends(get_db)):
    data = db.query(SomeModel).all()
    meta = build_meta_tags(title="My Page", site_title=settings.SITE_TITLE)
    tmpl = get_front_template("my_page.html")
    return tmpl.render(request=request, meta=meta, data=data)
```

**IMPORTANT**: Register new specific routes BEFORE the catch-all `/{slug}`.

### Adding a New Admin Route

In `app/routes/admin.py`:

```python
@router.get("/my-feature", response_class=HTMLResponse)
async def my_feature(request: Request, db: DBSession = Depends(get_db)):
    # request.state.user is set by AdminAuthMiddleware
    user = request.state.user
    tmpl = get_admin_template("my_feature.html")
    return tmpl.render(request=request, user=user)
```

### Adding a New API Endpoint

In `app/routes/api.py`:

```python
@router.get("/my-endpoint")
async def my_endpoint(db: DBSession = Depends(get_db)):
    data = db.query(Product).limit(10).all()
    return JSONResponse({"data": [p.name for p in data]})
```

## Authentication

### How Admin Auth Works

1. User visits `/admin/login`
2. POST username + password
3. `security.verify_password()` checks SHA-256 hash
4. `security.create_session()` stores session in DB
5. Cookie `zcore_session` set on response
6. `AdminAuthMiddleware` checks cookie on every `/admin/*` request
7. `request.state.user` is populated for route handlers

### Creating Admin Users

```bash
# Interactive
python3 scripts/create_admin.py

# Programmatic
from app.models.database import get_session, User, UserRole
from app.core.security import hash_password

db = get_session()
user = User(
    username="admin",
    email="admin@site.com",
    password_hash=hash_password("secure-password"),
    display_name="Admin",
    role=UserRole.ADMIN,
)
db.add(user)
db.commit()
```

### Changing Passwords

```bash
python3 scripts/create_admin.py
# Enter same username → updates password
```

## Image Handling

### Upload Flow

```python
from app.utils.image import get_upload_path, convert_to_webp, create_thumbnail

# 1. Save uploaded file
file_path = get_upload_path(filename, "products")
file_path.write_bytes(file_bytes)

# 2. Convert to WebP
webp_path = convert_to_webp(str(file_path))

# 3. Create thumbnail
thumb_path = create_thumbnail(str(file_path), max_size=(400, 400))

# 4. Store relative URL in database
url = "/" + str(webp_path).replace(str(STATIC_DIR) + "/", "")
```

### File Organization

```
app/static/uploads/
├── products/
│   └── 2026/05/
│       ├── iphone-15-pro-a1b2c3.webp
│       └── iphone-15-pro-a1b2c3-thumb.webp
├── posts/
│   └── 2026/05/
│       └── top-10-phones-d4e5f6.webp
└── logo.png
```

Files are organized by `YYYY/MM/` subdirectories. Filenames are
SEO-slugified with a short hash suffix to prevent collisions.

## Notifications

### Telegram Setup

1. Create bot via @BotFather → get token
2. Get chat ID (send message to bot, check `https://api.telegram.org/bot<TOKEN>/getUpdates`)
3. Set in `.env`:
   ```
   ZCORE_TELEGRAM_BOT_TOKEN=123456:ABC-DEF
   ZCORE_TELEGRAM_CHAT_ID=-100123456789
   ```

### Email Setup (Gmail)

1. Enable 2FA on Google account
2. Generate App Password: Google Account → Security → App Passwords
3. Set in `.env`:
   ```
   ZCORE_SMTP_HOST=smtp.gmail.com
   ZCORE_SMTP_PORT=587
   ZCORE_SMTP_USER=you@gmail.com
   ZCORE_SMTP_PASS=xxxx-xxxx-xxxx-xxxx
   ZCORE_SMTP_FROM=you@gmail.com
   ```

## Testing

### Seed Test Data

```bash
python3 scripts/seed.py
# Creates: 1000 products, 15 posts, 4 pages, 20 orders
# Admin: admin/admin123
```

### Run Audit

```bash
# Start server first
python3 -m app.main &

# Run audit
python3 scripts/audit.py
# Tests: performance, security, stability, data integrity
```

### Manual Testing Checklist

- [ ] Homepage loads with featured products
- [ ] Shop page paginates correctly
- [ ] Product detail shows variants
- [ ] Search returns relevant results
- [ ] Cart adds/removes items
- [ ] Checkout creates order
- [ ] Admin login works
- [ ] Admin can create/edit/delete posts
- [ ] Admin can create/edit/delete products
- [ ] Admin can view/update orders
- [ ] Sitemap.xml generates correctly
- [ ] 404 page shows for missing routes

## Common Tasks

### Add a New Static Page

```python
# In admin panel: /admin/pages/new
# Or programmatically:
from app.models.database import get_session, Page, PostStatus
from datetime import datetime, timezone

db = get_session()
page = Page(
    title="Chính sách bảo hành",
    slug="chinh-sach-bao-hanh",
    content="## Nội dung chính sách...",
    status=PostStatus.PUBLISHED,
    published_at=datetime.now(timezone.utc),
)
db.add(page)
db.commit()
```

### Add a Product Category

```python
from app.models.database import get_session, Category

db = get_session()
cat = Category(name="Phụ kiện", slug="phu-kien", description="Phụ kiện điện thoại")
db.add(cat)
db.commit()
```

### Customize the Homepage

Edit `app/templates/front/home.html`. The homepage shows:
1. Hero section (site title + description)
2. Featured products (8 items, `is_featured=True`)
3. Categories (top-level only)
4. Recent posts (6 items)

### Change Admin Panel URL

In `.env`:
```
ZCORE_ADMIN_PREFIX=/dashboard
```

This changes `/admin/*` to `/dashboard/*`.

## Troubleshooting

### Database Locked Error

SQLite allows only one writer at a time. If you get "database is locked":
- WAL mode should prevent this for reads
- For writes, the `busy_timeout=5000` PRAGMA waits 5 seconds
- If still locked, check for long-running transactions

### Template Not Found

- Check file exists in `app/templates/front/` or `app/templates/admin/`
- Check the template name in `get_front_template("name.html")`
- Jinja2 is case-sensitive

### Static Files Not Updating

- Nginx caches static files (30d expiry in config)
- For dev: disable Nginx or add cache-busting query param
- For production: update Nginx config to shorter expiry during development

### Migration Import Errors

- Check XML file encoding (should be UTF-8)
- For MySQL: ensure pymysql is installed (`pip install pymysql`)
- Check database credentials and network access
- Review error messages in migration output
