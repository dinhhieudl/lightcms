# Z-Core Framework

A lightweight, blazing-fast CMS framework designed to replace WordPress.

## Architecture

- **Backend:** Python 3.11+ / FastAPI
- **Database:** SQLite (single file, zero-maintenance)
- **Template:** Jinja2 (server-side rendering)
- **Frontend:** Tailwind CSS (standalone CLI)
- **Storage:** Local filesystem with WebP auto-conversion
- **Deployment:** Docker + Nginx reverse proxy (FastPanel compatible)

## Quick Start

```bash
# Development
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m app.main

# Production (Docker)
docker build -t zcore -f docker/Dockerfile .
docker run -d -p 8000:8000 -v ./data:/app/data zcore
```

## Directory Structure

```
lightcms/
├── app/
│   ├── core/           # Framework core (config, database, security)
│   ├── models/         # SQLAlchemy ORM models
│   ├── routes/         # URL routing (admin + frontend)
│   ├── services/       # Business logic layer
│   ├── middleware/      # Request/response middleware
│   ├── utils/          # Helpers (image, markdown, seo)
│   ├── templates/      # Jinja2 templates
│   │   ├── admin/      # Admin panel templates
│   │   ├── front/      # Public-facing templates
│   │   ├── components/ # Reusable template components
│   │   └── layouts/    # Base layouts
│   ├── static/         # Static assets
│   └── main.py         # Application entry point
├── migrations/         # Database migration scripts
│   ├── wp_migrate.py   # WordPress migration engine
│   └── schema.sql      # Reference schema
├── scripts/            # Deployment & utility scripts
│   ├── deploy.sh       # Zero-downtime deploy
│   ├── build_css.sh    # Tailwind CSS build
│   └── backup.sh       # Database backup
├── config/             # Configuration files
│   ├── settings.py     # App settings
│   └── nginx.conf      # Nginx reverse proxy config
├── docker/             # Docker files
│   ├── Dockerfile      # Multi-stage build (<100MB)
│   └── docker-compose.yml
├── docs/               # Documentation
└── tests/              # Test suite
```

## WordPress Migration

```bash
# From MySQL dump
python -m migrations.wp_migrate --source mysql --host localhost --db wp_db --user wp_user --pass wp_pass

# From WordPress XML Export
python -m migrations.wp_migrate --source xml --file export.xml
```

## License

MIT
