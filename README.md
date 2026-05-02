# Z-Core Framework

A lightweight, blazing-fast CMS framework designed to replace WordPress.

**Stack:** Python/FastAPI + SQLite (WAL) + Jinja2 SSR + Tailwind CSS

## Quick Start

```bash
git clone https://github.com/dinhhieudl/lightcms.git
cd lightcms
./scripts/setup.sh          # Creates venv, .env, DB, admin user
python3 -m app.main         # → http://localhost:8000
```

Admin panel: `http://localhost:8000/admin` (login created during setup)

## Features

- **Blog**: Posts with Markdown, categories, tags, SEO meta
- **E-commerce**: Products, variants (color/size), stock management
- **Orders**: Cart (LocalStorage) → Checkout → Telegram/Email notification
- **Admin Panel**: Lightweight CRUD for all content types
- **SEO**: Auto sitemap.xml, robots.txt, meta tags, URL preservation
- **Migration**: Import from WordPress XML or MySQL directly
- **Security**: SHA-256+salt passwords, XSS/SQLi protection, security headers

## Performance (1000 products, single worker)

| Endpoint | Avg Response |
|----------|-------------|
| Homepage | 3.2ms |
| Shop | 3.7ms |
| Product | 6.4ms |
| Search | 2.4ms |
| DB Query | 0.01-0.16ms |

## Documentation

| Doc | Description |
|-----|-------------|
| [Architecture](docs/architecture.md) | Deep dive: DB schema, routing, security, templates, performance |
| [Development](docs/development.md) | Dev setup, adding routes/templates/models, testing |
| [Deployment](docs/deployment.md) | Production deploy: systemd, Docker, FastPanel, Nginx |
| [WordPress Migration](docs/migration.md) | Import from WordPress XML/MySQL |

## Directory Structure

```
lightcms/
├── app/
│   ├── core/           # Security, templates
│   ├── models/         # SQLAlchemy ORM (17 tables)
│   ├── routes/         # Admin + Frontend + API
│   ├── services/       # Notifications (Telegram/Email)
│   ├── middleware/      # Auth, security headers
│   ├── utils/          # Image, SEO helpers
│   ├── templates/      # 23 Jinja2 templates
│   └── static/         # CSS, JS, uploads
├── migrations/         # WordPress migration engine
├── scripts/            # deploy, backup, seed, audit
├── config/             # Settings, Nginx config
├── docker/             # Dockerfile, compose
└── docs/               # Documentation
```

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/setup.sh` | First-run setup (venv, deps, DB, admin) |
| `scripts/deploy.sh` | Zero-downtime deploy with auto-rollback |
| `scripts/backup.sh` | SQLite safe backup |
| scripts/seed.py | Generate 1000 test products |
| scripts/audit.py | Performance + security + stability audit |
| scripts/create_admin.py | Create/reset admin user |
| scripts/build_css.sh | Build Tailwind CSS |

## WordPress Migration

```bash
# From XML export
python3 -m migrations.wp_migrate --source xml --file export.xml

# From MySQL
python3 -m migrations.wp_migrate --source mysql \
    --host localhost --db wordpress --user root --pass secret
```

Preserves: URLs, posts, pages, products, categories, tags, SEO meta (Yoast/RankMath).

## Deployment

```bash
# Direct (systemd)
./scripts/setup.sh
sudo systemctl enable zcore

# Docker
docker build -t zcore -f docker/Dockerfile .
docker run -d -p 8000:8000 -v zcore-data:/app/data zcore

# Update
./scripts/deploy.sh
```

See [Deployment Guide](docs/deployment.md) for full instructions.

## License

MIT
