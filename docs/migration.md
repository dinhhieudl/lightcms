# Z-Core WordPress Migration Guide

## Overview

Z-Core includes a built-in migration engine that converts WordPress/WooCommerce data to Z-Core's SQLite database.

Supports two sources:
- **WordPress XML Export (WXR)** — recommended, no server access needed
- **MySQL Direct Connection** — for live migrations

## Method 1: XML Export (Recommended)

### 1. Export from WordPress

1. Go to WordPress Admin → **Tools** → **Export**
2. Select **All content**
3. Click **Download Export File**
4. Save the `.xml` file

### 2. Run Migration

```bash
source venv/bin/activate
python -m migrations.wp_migrate --source xml --file /path/to/export.xml
```

### What Gets Migrated

| WordPress | Z-Core | Notes |
|-----------|--------|-------|
| Posts | `posts` table | HTML → Markdown, shortcodes stripped |
| Pages | `pages` table | Content converted |
| Categories | `categories` table | Hierarchy preserved |
| Tags | `tags` table | — |
| Users | `users` table | Password reset required (default: `changeme123`) |
| WooCommerce Products | `products` table | SKU, price, stock, attributes |
| Attachments | `media` table | URLs preserved for download |

### 3. Post-Migration Checklist

- [ ] Change admin password
- [ ] Review imported content (some HTML may need cleanup)
- [ ] Set up redirects for old URLs
- [ ] Upload media files to `/static/uploads/`
- [ ] Configure SEO meta descriptions
- [ ] Test all product pages

## Method 2: MySQL Direct

### Requirements

```bash
pip install pymysql
```

### Run

```bash
python -m migrations.wp_migrate \
    --source mysql \
    --host localhost \
    --db wordpress \
    --user root \
    --pass yourpassword \
    --prefix wp_
```

## URL Mapping

| WordPress URL | Z-Core URL |
|---------------|------------|
| `/?p=123` | `/blog/{slug}` |
| `/blog/post-name/` | `/blog/post-name/` |
| `/product/product-name/` | `/product/product-name/` |
| `/category/cat-name/` | `/shop?category=cat-name` |
| `/page-name/` | `/{page-name}` |

## SEO Preservation

The migration engine:
1. Preserves all post/page slugs (keeping URLs identical)
2. Imports Yoast/RankMath/AIOSEO meta data
3. Creates redirect entries for changed URLs
4. Generates `sitemap.xml` automatically

## Troubleshooting

**Content looks broken after migration:**
- WordPress shortcodes are stripped during conversion
- Some complex HTML layouts may need manual cleanup
- Review content in Admin → Posts → Edit

**Missing images:**
- XML export doesn't include image files
- Manually download `wp-content/uploads/` to `/static/uploads/`
- Update image paths in database if needed

**Duplicate slugs:**
- Z-Core auto-appends `-1`, `-2` etc. to duplicate slugs
- Review and fix in admin panel
