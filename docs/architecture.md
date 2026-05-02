# Z-Core Architecture Deep Dive

## Overview

Z-Core is a server-rendered CMS framework designed to replace WordPress. It prioritizes:
- **Speed**: SQLite + Jinja2 SSR, no client-side JS framework
- **Simplicity**: Single-file database, no build step required
- **SEO**: Preserves WordPress URL structure, auto-generates sitemaps
- **Low resource**: Runs on 512MB RAM VPS, no Node.js runtime needed

## Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Runtime | Python 3.11+ | Async support, rich ecosystem |
| Web Framework | FastAPI | Async, auto-docs, dependency injection |
| Database | SQLite 3 (WAL mode) | Zero-config, single file, concurrent reads |
| ORM | SQLAlchemy 2.0 | Mature, supports SQLite WAL |
| Templates | Jinja2 | Fast server-side rendering, auto-escaping |
| CSS | Tailwind CSS (standalone CLI) | Utility-first, no Node.js at runtime |
| Auth | Cookie sessions + SHA-256 salted passwords | Simple, secure for admin panel |
| Notifications | Telegram Bot API + SMTP | Instant order alerts |

## Request Lifecycle

```
Client Request
    │
    ▼
FastAPI Router
    │
    ├─ SecurityHeadersMiddleware    ← Adds X-Frame-Options, CSP, etc.
    ├─ SessionMiddleware            ← Parses session cookie
    ├─ AdminAuthMiddleware          ← Protects /admin/* routes
    │
    ▼
Route Handler (admin.py / frontend.py / api.py)
    │
    ├─ SQLAlchemy Session (per-request)
    ├─ Jinja2 Template Rendering
    │
    ▼
Response (HTML / JSON / Redirect)
```

## Database Architecture

### Design Principles

1. **Normalized**: No WordPress-style EAV (Entity-Attribute-Value) anti-pattern
2. **Foreign keys enforced**: `PRAGMA foreign_keys=ON`
3. **WAL mode**: Concurrent reads, non-blocking writes
4. **Indexed**: All slug, SKU, and lookup columns indexed

### Table Relationships

```
users ──────────┐
                 ├──── posts (author_id)
                 ├──── orders (customer_id)
                 └──── media (uploaded_by)

categories ─────┐
                 ├──── post_categories (junction)
                 ├──── product_categories (junction)
                 └──── self-referential (parent_id)

tags ────────────┬──── post_tags (junction)
                 └──── product_tags (junction)

products ────────┬──── product_variants
                 ├──── product_attributes
                 ├──── product_meta
                 └──── order_items

orders ──────────└──── order_items
```

### SQLite WAL Mode

Enabled via PRAGMA on every connection:
```sql
PRAGMA journal_mode=WAL;      -- Write-Ahead Logging for concurrent reads
PRAGMA foreign_keys=ON;        -- Enforce FK constraints
PRAGMA busy_timeout=5000;      -- Wait 5s on lock contention
```

WAL allows multiple readers while a writer is active. This is critical for
a web server where the admin might be editing while visitors are reading.

### Key Schema Decisions

**Posts vs Pages**: Separate tables (not `post_type` column like WordPress).
Reason: Different columns, different templates, cleaner queries.

**Product Variants**: Normalized `product_variants` table instead of
WordPress meta_key/meta_value soup. Each variant has its own price, stock, SKU.

**SEO Fields**: Inline on posts/pages/products (not a separate table).
Meta title, description, canonical URL, OG image are always 1:1 with content.

**Orders**: Snapshot-based. `order_items` stores product name/price at
order time, so product changes don't affect historical orders.

## Template Architecture

### Rendering Pipeline

```python
# In app/core/templates.py
env = Environment(
    loader=FileSystemLoader("app/templates/"),
    autoescape=select_autoescape(["html"]),  # XSS protection
    trim_blocks=True,
    lstrip_blocks=True,
)
```

### Template Hierarchy

```
layouts/
  base.html          ← HTML skeleton, meta tags, CSS/JS
  admin_base.html    ← Admin sidebar + content area

components/
  header.html        ← Nav, search, cart badge
  footer.html        ← Links, copyright, cart JS

front/               ← Public-facing pages
  home.html          ← Homepage (featured products + recent posts)
  shop.html          ← Product listing with filters
  product.html       ← Single product with variants
  blog.html          ← Post listing
  post.html          ← Single post
  cart.html          ← Cart (LocalStorage-based)
  checkout.html      ← Order form
  search.html        ← Search results
  page.html          ← Static pages
  404.html           ← Not found
  order_success.html ← Order confirmation

admin/               ← Admin panel
  login.html         ← Authentication
  dashboard.html     ← Stats + recent activity
  posts/list.html    ← Post listing
  posts/edit.html    ← Post editor (Markdown)
  pages/list.html    ← Page listing
  pages/edit.html    ← Page editor
  products/list.html ← Product listing
  products/edit.html ← Product editor
  orders/list.html   ← Order listing with filters
  orders/detail.html ← Order detail + status update
  categories/list.html ← Category management
  settings.html      ← Site settings
```

### Custom Jinja2 Filters

| Filter | Usage | Example |
|--------|-------|---------|
| `format_price` | VND formatting | `{{ 150000\|format_price }}` → `150.000₫` |
| `timeago` | Relative time | `{{ dt\|timeago }}` → `3 giờ trước` |
| `markdown` | MD → HTML | `{{ content\|markdown\|safe }}` |
| `truncate_html` | Strip HTML + truncate | `{{ text\|truncate_html(160) }}` |
| `slugify` | URL-safe slug | `{{ name\|slugify }}` |
| `tojson` | JSON serialize | `{{ data\|tojson }}` |

### Global Template Variables

Available in all templates:
- `site_url`, `site_title`, `site_description`, `site_language`
- `admin_prefix` (default: `/admin`)
- `app_version`
- `now` (current datetime)

## Routing Architecture

### Route Registration Order (Critical!)

FastAPI matches routes in registration order. First match wins.

```python
# In app/main.py
app.include_router(admin_router, prefix="/admin")   # 1. Admin routes
app.include_router(api_router, prefix="/api")        # 2. API routes
app.include_router(frontend_router)                   # 3. Frontend (catch-all last)
```

Within `frontend_router`, order MUST be:
1. `/` (homepage)
2. `/blog`, `/blog/{slug}` (specific)
3. `/shop`, `/product/{slug}` (specific)
4. `/search`, `/cart`, `/checkout`, `/order-success` (specific)
5. `/robots.txt`, `/sitemap.xml` (SEO)
6. `/{slug}` **CATCH-ALL** — must be last!

If `/{slug}` is registered before `/cart`, visiting `/cart` will match
the catch-all and return 404 (no page with slug "cart").

### Reserved Slugs

The catch-all `/{slug}` handles static pages only. These slugs are
reserved for framework routes and will return 404 if no explicit route
matches them: `search`, `shop`, `blog`, `cart`, `checkout`, `order-success`,
`api`, `admin`, `static`.

## Security Architecture

### Authentication Flow

```
1. POST /admin/login (username + password)
2. Verify: SHA-256(salt + password) vs stored hash
3. Create session: random 64-char key → sessions table
4. Set cookie: zcore_session=<key>, httponly, max_age=86400
5. Subsequent requests: AdminAuthMiddleware reads cookie → loads user
```

### Password Storage

```python
# Hash
salt = secrets.token_hex(16)  # 32 hex chars
h = sha256(salt + password)
stored = f"{salt}${h}"        # e.g. "a1b2c3...$e5f6g7..."

# Verify
salt, stored_hash = stored.split("$", 1)
computed = sha256(salt + input_password)
return compare_digest(computed, stored_hash)  # Constant-time
```

### CSRF Protection

Forms should include CSRF token. Currently the admin uses cookie-based
auth which provides some CSRF protection via SameSite cookie attribute.
For production, add CSRF token middleware.

### XSS Prevention

Jinja2 `autoescape=True` for all `.html` and `.xml` templates.
All user content is HTML-escaped by default. Use `|safe` filter only
for trusted content (e.g., Markdown rendered by the `|markdown` filter).

### SQL Injection Prevention

SQLAlchemy uses parameterized queries exclusively. No raw SQL string
concatenation. The migration engine also uses parameterized queries.

### Security Headers

Added via `SecurityHeadersMiddleware`:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy: default-src 'self'; ...`

## Cart & Checkout Architecture

### Client-Side Cart (LocalStorage)

The cart lives entirely in the browser's LocalStorage. No server-side
cart state. This eliminates cart abandonment from session timeouts.

```javascript
// Cart structure in localStorage
[
  {
    "product_id": 42,
    "variant_id": 101,     // null for simple products
    "name": "iPhone 15 Pro",
    "variant_name": "256GB / Đen",
    "image": "/static/uploads/...",
    "quantity": 2
  }
]
```

### Checkout Flow

```
1. User fills form (name, email, phone, address)
2. JS serializes cart → hidden input `cart_data`
3. POST /checkout
4. Server:
   a. Parse cart JSON
   b. Look up product prices from DB (don't trust client prices)
   c. Create Order + OrderItems
   d. Send Telegram + Email notifications (async)
   e. Decrease stock quantities
   f. Redirect to /order-success?order=ZC-20260502-ABC123
```

### Price Security

The server ALWAYS looks up current prices from the database.
The client-sent cart only contains product_id, variant_id, and quantity.
Prices are never trusted from the client.

## Migration Architecture

### Two Source Adapters

1. **WordPressXMLImporter**: Parses WXR (WordPress eXtended RSS) XML
   - No server access needed
   - Exports from WordPress Admin → Tools → Export
   - Handles posts, pages, products, categories, tags, media

2. **WordPressMySQLImporter**: Direct MySQL connection
   - Requires database credentials
   - Real-time migration from live WordPress
   - More complete (can read all meta)

### Content Conversion Pipeline

```
WordPress HTML Content
    │
    ├─ Strip shortcodes ([caption], [gallery], etc.)
    ├─ HTML → Markdown conversion
    │   ├─ Preserve code blocks
    │   ├─ Convert headings, lists, links, images
    │   ├─ Strip remaining HTML tags
    │   └─ Decode HTML entities
    ├─ Extract SEO meta (Yoast, RankMath, AIOSEO)
    │
    ▼
Clean Markdown Content
```

### URL Preservation

Migration preserves all WordPress URLs:
- `/blog/post-slug/` → `/blog/post-slug/` (identical)
- `/product/product-slug/` → `/product/product-slug/` (identical)
- `/page-slug/` → `/page-slug/` (identical)

For changed URLs, the `redirects` table stores 301 mappings.

## Performance Characteristics

### Why It's Fast

1. **SQLite**: No network roundtrip, data is on local disk
2. **WAL mode**: Concurrent reads don't block writes
3. **Server-side rendering**: No JS framework hydration delay
4. **No ORM overhead in hot path**: Simple queries, indexed columns
5. **Small response sizes**: 14-20 KB per page (no React bundle)

### Benchmarks (1000 products, single worker)

| Operation | Time |
|-----------|------|
| Homepage render | 3ms |
| Shop page (12 products) | 4ms |
| Product detail | 6ms |
| Full-text search | 2.5ms |
| DB query (indexed) | 0.01-0.16ms |
| 100 sequential requests | 4.1ms avg |

### Scaling Notes

- **SQLite reads**: Unlimited concurrent readers (WAL mode)
- **SQLite writes**: Serialized (one writer at a time)
- **Recommended**: 1 writer (admin) + many readers (visitors)
- **For >10k products**: Consider adding Redis cache layer
- **For >100k daily users**: Migrate to PostgreSQL (schema compatible)

## Deployment Architecture

### Production Stack

```
Internet
    │
    ▼
Nginx (reverse proxy)
    ├─ Static files: /static/ (served directly by Nginx)
    ├─ Gzip compression
    ├─ Security headers
    ├─ SSL termination (Let's Encrypt)
    │
    ▼
FastAPI (uvicorn)
    ├─ --workers 2-4 (one per CPU core)
    ├─ --host 127.0.0.1 (internal only)
    ├─ --port 8000
    │
    ▼
SQLite (data/zcore.db)
    └─ WAL mode, backed up daily
```

### Docker Architecture

Multi-stage build for minimal image size:
- Stage 1: Install Python dependencies (build layer)
- Stage 2: Copy only installed packages + app code
- Final image: ~80MB (Python slim + deps)
- Non-root user (`zcore`)
- Health check via HTTP probe

### File Structure on Server

```
/opt/zcore/
├── app/                    # Application code (git-managed)
├── config/                 # Nginx config template
├── data/
│   ├── zcore.db           # SQLite database (persistent volume)
│   ├── zcore.db-wal       # WAL journal
│   └── zcore.db-shm       # Shared memory
├── backups/                # Auto-backups before deploy
├── .env                    # Secrets (not in git)
├── .env.example            # Template
├── requirements.txt        # Python dependencies
├── scripts/
│   ├── deploy.sh           # Zero-downtime deploy
│   ├── backup.sh           # Database backup
│   └── setup.sh            # First-run setup
└── venv/                   # Python virtual environment
```

## API Reference

### Public API (`/api/`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/products` | List products (paginated, filterable) |
| GET | `/api/products/{id}` | Product detail with variants |
| GET | `/api/search?q=` | Search products + posts |

### Admin Routes (`/admin/`)

All require cookie authentication.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/login` | Login page |
| POST | `/admin/login` | Authenticate |
| GET | `/admin/logout` | Destroy session |
| GET | `/admin/` | Dashboard |
| GET/POST | `/admin/posts` | List/create posts |
| GET/POST | `/admin/posts/{id}/edit` | Edit post |
| GET/POST | `/admin/pages` | List/create pages |
| GET/POST | `/admin/products` | List/create products |
| GET/POST | `/admin/orders` | List orders |
| GET/POST | `/admin/orders/{id}` | Order detail |
| GET/POST | `/admin/categories` | Manage categories |
| GET/POST | `/admin/settings` | Site settings |

### Frontend Routes

| Path | Description |
|------|-------------|
| `/` | Homepage |
| `/shop` | Product listing |
| `/shop?category=slug` | Filtered by category |
| `/shop?sort=price_asc` | Sorted products |
| `/product/{slug}` | Product detail |
| `/blog` | Blog listing |
| `/blog/{slug}` | Blog post |
| `/search?q=` | Search results |
| `/cart` | Shopping cart |
| `/checkout` | Order form |
| `/order-success?order=` | Order confirmation |
| `/{slug}` | Static pages (catch-all) |
| `/robots.txt` | Robots file |
| `/sitemap.xml` | XML sitemap |
