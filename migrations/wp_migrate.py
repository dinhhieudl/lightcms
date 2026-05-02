"""
Z-Core WordPress Migration Engine
==================================
Migrates data from WordPress/WooCommerce to Z-Core SQLite.

Supports two sources:
  1. MySQL direct connection
  2. WordPress XML Export (WXR)

Usage:
  # From MySQL
  python -m migrations.wp_migrate --source mysql --host localhost --db wordpress --user root --pass secret

  # From XML export
  python -m migrations.wp_migrate --source xml --file export.xml
"""

import argparse
import hashlib
import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.database import (
    init_db, get_session, get_engine,
    User, Post, Page, Product, ProductVariant, ProductAttribute,
    Category, Tag, PostMeta, ProductMeta, Media, Redirect, Option,
    PostStatus, ProductStatus, UserRole
)
from app.core.security import hash_password
from config import settings

# ── HTML to Markdown Converter ─────────────────────────────────────────

class HTMLToMarkdown:
    """Basic HTML to Markdown converter for WordPress content."""

    def convert(self, html_text: str) -> str:
        if not html_text:
            return ""

        text = html_text

        # Preserve code blocks
        code_blocks = []
        def save_code(m):
            code_blocks.append(m.group(0))
            return f"__CODE_BLOCK_{len(code_blocks)-1}__"
        text = re.sub(r"<pre[^>]*>.*?</pre>", save_code, text, flags=re.DOTALL)
        text = re.sub(r"<code[^>]*>.*?</code>", save_code, text, flags=re.DOTALL)

        # Headers
        for i in range(6, 0, -1):
            text = re.sub(rf"<h{i}[^>]*>(.*?)</h{i}>", rf"\n{'#' * i} \1\n", text, flags=re.DOTALL)

        # Bold / Italic
        text = re.sub(r"<(strong|b)>(.*?)</\1>", r"**\2**", text, flags=re.DOTALL)
        text = re.sub(r"<(em|i)>(.*?)</\1>", r"*\2*", text, flags=re.DOTALL)

        # Links
        text = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r"[\2](\1)", text, flags=re.DOTALL)

        # Images
        text = re.sub(r'<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"[^>]*/?>',
                       r"![\2](\1)", text)
        text = re.sub(r'<img[^>]*src="([^"]*)"[^>]*/?>', r"![](\1)", text)

        # Lists
        text = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1", text, flags=re.DOTALL)
        text = re.sub(r"</?[ou]l[^>]*>", "", text)

        # Blockquotes
        text = re.sub(r"<blockquote[^>]*>(.*?)</blockquote>",
                       lambda m: "\n> " + m.group(1).strip().replace("\n", "\n> ") + "\n",
                       text, flags=re.DOTALL)

        # Paragraphs & line breaks
        text = re.sub(r"<br\s*/?>", "\n", text)
        text = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", text, flags=re.DOTALL)

        # Remove remaining HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Decode HTML entities
        text = html.unescape(text)

        # Clean up whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()

        # Restore code blocks
        for i, block in enumerate(code_blocks):
            text = text.replace(f"__CODE_BLOCK_{i}__", block)

        return text


html2md = HTMLToMarkdown()


# ── Shortcode Handler ──────────────────────────────────────────────────

def strip_shortcodes(content: str) -> str:
    """Remove WordPress shortcodes, keep inner text where possible."""
    # [caption]...[/caption] → keep inner
    content = re.sub(r"\[caption[^\]]*\](.*?)\[/caption\]", r"\1", content, flags=re.DOTALL)
    # [gallery] → placeholder
    content = re.sub(r"\[gallery[^\]]*\]", "[Gallery images — check media library]", content)
    # Strip remaining shortcodes
    content = re.sub(r"\[[\w\s=/\"'.,\-]+\]", "", content)
    return content


def clean_content(wp_content: str) -> str:
    """Convert WordPress HTML content to clean Markdown."""
    content = strip_shortcodes(wp_content)
    content = html2md.convert(content)
    return content


# ── WordPress XML (WXR) Parser ─────────────────────────────────────────

WXR_NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "wp": "http://wordpress.org/export/1.2/",
    "excerpt": "http://wordpress.org/export/1.2/excerpt/",
    "dc": "http://purl.org/dc/elements/1.1/",
}


class WordPressXMLImporter:
    """Import from WordPress eXtended RSS (WXR) export file."""

    def __init__(self, xml_path: str):
        self.xml_path = xml_path
        self.tree = None
        self.db = get_session()
        self.stats = {
            "users": 0, "posts": 0, "pages": 0, "categories": 0,
            "tags": 0, "media": 0, "products": 0, "errors": []
        }
        self.user_map = {}  # wp_user_id → zcore_user_id
        self.term_map = {}  # wp_term_id → zcore_cat/tag_id
        self.post_map = {}  # wp_post_id → zcore_post/product_id

    def parse(self):
        """Parse XML file."""
        print(f"📄 Parsing {self.xml_path}...")
        self.tree = ET.parse(self.xml_path)
        self.root = self.tree.getroot()
        channel = self.root.find("channel")

        # Get site info
        title = channel.findtext("title", "")
        link = channel.findtext("link", "")
        description = channel.findtext("description", "")
        print(f"   Site: {title} ({link})")

        # Process in order
        self._import_categories(channel)
        self._import_tags(channel)
        self._import_users(channel)
        self._import_items(channel)

        self.db.close()
        return self.stats

    def _import_categories(self, channel):
        """Import categories from XML."""
        for cat in channel.findall("wp:category", WXR_NS):
            term_id = cat.findtext("wp:term_id", "", WXR_NS)
            cat_nicename = cat.findtext("wp:category_nicename", "", WXR_NS)
            cat_name = cat.findtext("wp:cat_name", "", WXR_NS)
            parent = cat.findtext("wp:category_parent", "", WXR_NS)

            existing = self.db.query(Category).filter(Category.slug == cat_nicename).first()
            if not existing:
                new_cat = Category(name=cat_name, slug=cat_nicename)
                self.db.add(new_cat)
                self.db.flush()
                self.term_map[term_id] = new_cat.id
                self.stats["categories"] += 1
            else:
                self.term_map[term_id] = existing.id

        self.db.commit()
        print(f"   ✅ Categories: {self.stats['categories']}")

    def _import_tags(self, channel):
        """Import tags from XML."""
        for tag_el in channel.findall("wp:tag", WXR_NS):
            term_id = tag_el.findtext("wp:term_id", "", WXR_NS)
            tag_slug = tag_el.findtext("wp:tag_slug", "", WXR_NS)
            tag_name = tag_el.findtext("wp:tag_name", "", WXR_NS)

            existing = self.db.query(Tag).filter(Tag.slug == tag_slug).first()
            if not existing:
                new_tag = Tag(name=tag_name, slug=tag_slug)
                self.db.add(new_tag)
                self.db.flush()
                self.term_map[term_id] = new_tag.id
                self.stats["tags"] += 1
            else:
                self.term_map[term_id] = existing.id

        self.db.commit()
        print(f"   ✅ Tags: {self.stats['tags']}")

    def _import_users(self, channel):
        """Import users from XML."""
        seen = set()
        for item in channel.findall("item"):
            dc_creator = item.findtext("dc:creator", "", WXR_NS)
            if dc_creator and dc_creator not in seen:
                seen.add(dc_creator)
                existing = self.db.query(User).filter(User.username == dc_creator).first()
                if not existing:
                    user = User(
                        username=dc_creator,
                        email=f"{dc_creator}@migrated.local",
                        password_hash=hash_password("changeme123"),
                        display_name=dc_creator,
                        role=UserRole.AUTHOR,
                    )
                    self.db.add(user)
                    self.db.flush()
                    self.user_map[dc_creator] = user.id
                    self.stats["users"] += 1

        self.db.commit()
        print(f"   ✅ Users: {self.stats['users']}")

    def _import_items(self, channel):
        """Import posts, pages, products, and media."""
        items = channel.findall("item")
        print(f"   📦 Found {len(items)} items to process...")

        for item in items:
            post_type = item.findtext("wp:post_type", "", WXR_NS)
            status_map = {
                "publish": PostStatus.PUBLISHED,
                "draft": PostStatus.DRAFT,
                "pending": PostStatus.PENDING,
                "trash": PostStatus.TRASH,
            }
            wp_status = item.findtext("wp:status", "", WXR_NS)
            status = status_map.get(wp_status, PostStatus.DRAFT)

            if post_type == "post":
                self._import_post(item, status)
            elif post_type == "page":
                self._import_page(item, status)
            elif post_type == "product":
                self._import_product(item, status)
            elif post_type == "attachment":
                self._import_attachment(item)

        self.db.commit()

    def _import_post(self, item, status):
        """Import a single post."""
        title = item.findtext("title", "")
        link = item.findtext("link", "")
        slug = item.findtext("wp:post_name", "", WXR_NS)
        content_raw = item.findtext("content:encoded", "", WXR_NS)
        excerpt_raw = item.findtext("excerpt:encoded", "", WXR_NS)
        creator = item.findtext("dc:creator", "", WXR_NS)
        pub_date = item.findtext("wp:post_date", "", WXR_NS)

        # Extract slug from link if missing
        if not slug and link:
            slug = link.rstrip("/").split("/")[-1]

        # Check for duplicate
        if self.db.query(Post).filter(Post.slug == slug).first():
            return

        # Clean content
        content = clean_content(content_raw)
        excerpt = clean_content(excerpt_raw) if excerpt_raw else ""

        # Parse date
        published_at = None
        if pub_date:
            try:
                published_at = datetime.strptime(pub_date, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

        # Get author
        author_id = self.user_map.get(creator)

        # Get featured image
        post_id = item.findtext("wp:post_id", "", WXR_NS)
        attachment_url = ""
        for postmeta in item.findall("wp:postmeta", WXR_NS):
            key = postmeta.findtext("wp:meta_key", "", WXR_NS)
            val = postmeta.findtext("wp:meta_value", "", WXR_NS)
            if key == "_thumbnail_id":
                # Find attachment URL
                att = self.db.query(Media).filter(Media.id == int(val)).first()
                if att:
                    attachment_url = "/" + att.file_path

        post = Post(
            title=title,
            slug=slug,
            content=content,
            excerpt=excerpt[:500] if excerpt else "",
            status=status,
            author_id=author_id,
            featured_image=attachment_url,
            published_at=published_at,
        )

        # Categories & tags from terms
        for cat_el in item.findall("category", ):
            domain = cat_el.get("domain", "")
            nicename = cat_el.get("nicename", "")
            term_id = cat_el.get("term_id", "")

            if domain == "category":
                cat = self.db.query(Category).filter(Category.slug == nicename).first()
                if cat:
                    post.categories.append(cat)
            elif domain == "post_tag":
                tag = self.db.query(Tag).filter(Tag.slug == nicename).first()
                if tag:
                    post.tags.append(tag)

        # SEO meta from plugins (Yoast, RankMath, AIOSEO)
        for postmeta in item.findall("wp:postmeta", WXR_NS):
            key = postmeta.findtext("wp:meta_key", "", WXR_NS)
            val = postmeta.findtext("wp:meta_value", "", WXR_NS)
            if key in ("_yoast_wpseo_metadesc", "_yoast_wpseo_title"):
                if "desc" in key:
                    post.meta_description = val
                elif "title" in key:
                    post.meta_title = val
            elif key == "_yoast_wpseo_canonical":
                post.canonical_url = val

        self.db.add(post)
        self.db.flush()
        self.post_map[post_id] = post.id
        self.stats["posts"] += 1

    def _import_page(self, item, status):
        """Import a single page."""
        title = item.findtext("title", "")
        slug = item.findtext("wp:post_name", "", WXR_NS)
        content_raw = item.findtext("content:encoded", "", WXR_NS)
        pub_date = item.findtext("wp:post_date", "", WXR_NS)

        if self.db.query(Page).filter(Page.slug == slug).first():
            return

        content = clean_content(content_raw)
        published_at = None
        if pub_date:
            try:
                published_at = datetime.strptime(pub_date, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass

        page = Page(
            title=title,
            slug=slug,
            content=content,
            status=status,
            published_at=published_at,
        )
        self.db.add(page)
        self.stats["pages"] += 1

    def _import_product(self, item, status):
        """Import a WooCommerce product."""
        title = item.findtext("title", "")
        slug = item.findtext("wp:post_name", "", WXR_NS)
        content_raw = item.findtext("content:encoded", "", WXR_NS)
        excerpt_raw = item.findtext("excerpt:encoded", "", WXR_NS)

        if self.db.query(Product).filter(Product.slug == slug).first():
            return

        content = clean_content(content_raw)
        excerpt = clean_content(excerpt_raw) if excerpt_raw else ""

        # Parse WooCommerce meta
        meta = {}
        for postmeta in item.findall("wp:postmeta", WXR_NS):
            key = postmeta.findtext("wp:meta_key", "", WXR_NS)
            val = postmeta.findtext("wp:meta_value", "", WXR_NS)
            meta[key] = val

        product = Product(
            name=title,
            slug=slug,
            description=content,
            short_description=excerpt[:500] if excerpt else "",
            sku=meta.get("_sku", ""),
            price=float(meta.get("_regular_price", 0) or 0),
            sale_price=float(meta.get("_sale_price", 0) or 0) or None,
            stock_quantity=int(meta.get("_stock", 0) or 0),
            stock_status=meta.get("_stock_status", "instock"),
            manage_stock=meta.get("_manage_stock", "no") == "yes",
            product_type=meta.get("_product_type", "simple"),
            is_virtual=meta.get("_virtual", "no") == "yes",
            is_downloadable=meta.get("_downloadable", "no") == "yes",
            weight=float(meta.get("_weight", 0) or 0) or None,
            length=float(meta.get("_length", 0) or 0) or None,
            width=float(meta.get("_width", 0) or 0) or None,
            height=float(meta.get("_height", 0) or 0) or None,
            status=status,
        )

        # Categories
        for cat_el in item.findall("category"):
            if cat_el.get("domain") == "product_cat":
                nicename = cat_el.get("nicename", "")
                cat = self.db.query(Category).filter(Category.slug == nicename).first()
                if cat:
                    product.categories.append(cat)

        # Tags
        for tag_el in item.findall("category"):
            if tag_el.get("domain") == "product_tag":
                nicename = tag_el.get("nicename", "")
                tag = self.db.query(Tag).filter(Tag.slug == nicename).first()
                if tag:
                    product.tags.append(tag)

        # Parse attributes
        attr_names = meta.get("attribute_names", "")
        if isinstance(attr_names, str) and attr_names:
            try:
                attr_names = json.loads(attr_names)
            except (json.JSONDecodeError, TypeError):
                attr_names = []

        if isinstance(attr_names, list):
            for i, name in enumerate(attr_names):
                values_key = f"attribute_values[{i}]"
                attr_values = meta.get(values_key, "")
                if attr_values:
                    try:
                        values = json.loads(attr_values)
                    except (json.JSONDecodeError, TypeError):
                        values = [attr_values]
                    pa = ProductAttribute(
                        product=product,
                        name=name,
                        values=json.dumps(values),
                        is_variation=meta.get(f"attribute_variation[{i}]", "0") == "1",
                    )
                    self.db.add(pa)

        self.db.add(product)
        self.db.flush()
        post_id = item.findtext("wp:post_id", "", WXR_NS)
        self.post_map[post_id] = product.id
        self.stats["products"] += 1

    def _import_attachment(self, item):
        """Import a media attachment."""
        url = item.findtext("link", "")
        title = item.findtext("title", "")
        attachment_url = item.findtext("wp:attachment_url", "", WXR_NS)

        if not attachment_url:
            return

        media = Media(
            filename=os.path.basename(attachment_url),
            original_filename=os.path.basename(attachment_url),
            file_path=attachment_url,
            title=title,
            alt_text=title,
        )
        self.db.add(media)
        self.stats["media"] += 1


# ── MySQL Importer ─────────────────────────────────────────────────────

class WordPressMySQLImporter:
    """Import directly from WordPress MySQL database."""

    def __init__(self, host, port, db, user, password, table_prefix="wp_"):
        self.host = host
        self.port = port
        self.db_name = db
        self.user = user
        self.password = password
        self.prefix = table_prefix
        self.conn = None
        self.db = get_session()
        self.stats = {
            "users": 0, "posts": 0, "pages": 0, "categories": 0,
            "tags": 0, "products": 0, "media": 0, "errors": []
        }

    def connect(self):
        """Connect to MySQL."""
        try:
            import pymysql
            self.conn = pymysql.connect(
                host=self.host, port=self.port, user=self.user,
                password=self.password, database=self.db_name,
                charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor
            )
            print(f"✅ Connected to MySQL: {self.host}:{self.port}/{self.db_name}")
        except ImportError:
            print("❌ pymysql not installed. Run: pip install pymysql")
            sys.exit(1)

    def migrate(self):
        """Run full migration."""
        self.connect()
        self._migrate_users()
        self._migrate_categories()
        self._migrate_tags()
        self._migrate_posts()
        self._migrate_products()
        self._create_redirects()
        self.conn.close()
        self.db.close()
        return self.stats

    def _query(self, sql, params=None):
        """Execute MySQL query."""
        with self.conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            return cursor.fetchall()

    def _migrate_users(self):
        """Migrate WordPress users."""
        rows = self._query(f"SELECT * FROM {self.prefix}users")
        for row in rows:
            existing = self.db.query(User).filter(User.username == row["user_login"]).first()
            if existing:
                continue

            user = User(
                username=row["user_login"],
                email=row["user_email"],
                password_hash=hash_password("changeme123"),
                display_name=row["display_name"],
                role=UserRole.ADMIN if row["user_login"] == "admin" else UserRole.AUTHOR,
            )
            self.db.add(user)
            self.stats["users"] += 1
        self.db.commit()
        print(f"   ✅ Users: {self.stats['users']}")

    def _migrate_categories(self):
        """Migrate WordPress categories."""
        rows = self._query(f"""
            SELECT t.term_id, t.name, t.slug, tt.parent, tt.description
            FROM {self.prefix}terms t
            JOIN {self.prefix}term_taxonomy tt ON t.term_id = tt.term_id
            WHERE tt.taxonomy = 'category'
        """)
        for row in rows:
            existing = self.db.query(Category).filter(Category.slug == row["slug"]).first()
            if existing:
                continue
            cat = Category(
                name=row["name"],
                slug=row["slug"],
                description=row.get("description", ""),
            )
            self.db.add(cat)
            self.db.flush()
            self.stats["categories"] += 1
        self.db.commit()
        print(f"   ✅ Categories: {self.stats['categories']}")

    def _migrate_tags(self):
        """Migrate WordPress tags."""
        rows = self._query(f"""
            SELECT t.term_id, t.name, t.slug
            FROM {self.prefix}terms t
            JOIN {self.prefix}term_taxonomy tt ON t.term_id = tt.term_id
            WHERE tt.taxonomy = 'post_tag'
        """)
        for row in rows:
            existing = self.db.query(Tag).filter(Tag.slug == row["slug"]).first()
            if existing:
                continue
            tag = Tag(name=row["name"], slug=row["slug"])
            self.db.add(tag)
            self.stats["tags"] += 1
        self.db.commit()
        print(f"   ✅ Tags: {self.stats['tags']}")

    def _migrate_posts(self):
        """Migrate WordPress posts and pages."""
        rows = self._query(f"""
            SELECT p.*, u.user_login as author_login
            FROM {self.prefix}posts p
            LEFT JOIN {self.prefix}users u ON p.post_author = u.ID
            WHERE p.post_type IN ('post', 'page') AND p.post_status != 'auto-draft'
        """)

        for row in rows:
            slug = row["post_name"] or row["post_title"].lower().replace(" ", "-")
            post_type = row["post_type"]
            content = clean_content(row["post_content"])

            status_map = {
                "publish": PostStatus.PUBLISHED,
                "draft": PostStatus.DRAFT,
                "pending": PostStatus.PENDING,
                "trash": PostStatus.TRASH,
            }
            status = status_map.get(row["post_status"], PostStatus.DRAFT)

            if post_type == "post":
                if self.db.query(Post).filter(Post.slug == slug).first():
                    continue

                # Get featured image
                thumb_meta = self._query(f"""
                    SELECT meta_value FROM {self.prefix}postmeta
                    WHERE post_id = %s AND meta_key = '_thumbnail_id'
                """, (row["ID"],))
                featured_image = ""
                if thumb_meta:
                    att = self._query(f"""
                        SELECT guid FROM {self.prefix}posts WHERE ID = %s
                    """, (thumb_meta[0]["meta_value"],))
                    if att:
                        featured_image = att[0]["guid"]

                post = Post(
                    title=row["post_title"],
                    slug=slug,
                    content=content,
                    excerpt=clean_content(row.get("post_excerpt", "")),
                    status=status,
                    featured_image=featured_image,
                    published_at=row["post_date"] if row["post_date"] else None,
                )
                self.db.add(post)
                self.db.flush()

                # Categories
                cats = self._query(f"""
                    SELECT t.term_id FROM {self.prefix}term_relationships tr
                    JOIN {self.prefix}term_taxonomy tt ON tr.term_taxonomy_id = tt.term_taxonomy_id
                    JOIN {self.prefix}terms t ON tt.term_id = t.term_id
                    WHERE tr.object_id = %s AND tt.taxonomy = 'category'
                """, (row["ID"],))
                for c in cats:
                    cat = self.db.query(Category).filter(Category.slug.isnot(None)).first()
                    # Map by term_id
                    pass  # Simplified — full mapping requires term_id→category mapping

                self.stats["posts"] += 1

            elif post_type == "page":
                if self.db.query(Page).filter(Page.slug == slug).first():
                    continue
                page = Page(
                    title=row["post_title"],
                    slug=slug,
                    content=content,
                    status=status,
                    published_at=row["post_date"] if row["post_date"] else None,
                )
                self.db.add(page)
                self.stats["pages"] += 1

        self.db.commit()
        print(f"   ✅ Posts: {self.stats['posts']}, Pages: {self.stats['pages']}")

    def _migrate_products(self):
        """Migrate WooCommerce products."""
        rows = self._query(f"""
            SELECT p.* FROM {self.prefix}posts p
            WHERE p.post_type = 'product' AND p.post_status != 'auto-draft'
        """)

        for row in rows:
            slug = row["post_name"]
            if self.db.query(Product).filter(Product.slug == slug).first():
                continue

            # Get all meta
            meta_rows = self._query(f"""
                SELECT meta_key, meta_value FROM {self.prefix}postmeta
                WHERE post_id = %s
            """, (row["ID"],))
            meta = {m["meta_key"]: m["meta_value"] for m in meta_rows}

            status_map = {
                "publish": ProductStatus.PUBLISHED,
                "draft": ProductStatus.DRAFT,
                "pending": ProductStatus.PENDING,
                "trash": ProductStatus.TRASH,
            }
            status = status_map.get(row["post_status"], ProductStatus.DRAFT)

            product = Product(
                name=row["post_title"],
                slug=slug,
                description=clean_content(row["post_content"]),
                short_description=clean_content(row.get("post_excerpt", "")),
                sku=meta.get("_sku", ""),
                price=float(meta.get("_regular_price", 0) or 0),
                sale_price=float(meta.get("_sale_price", 0) or 0) or None,
                stock_quantity=int(meta.get("_stock", 0) or 0),
                stock_status=meta.get("_stock_status", "instock"),
                manage_stock=meta.get("_manage_stock", "no") == "yes",
                product_type=meta.get("_product_type", "simple"),
                weight=float(meta.get("_weight", 0) or 0) or None,
                length=float(meta.get("_length", 0) or 0) or None,
                width=float(meta.get("_width", 0) or 0) or None,
                height=float(meta.get("_height", 0) or 0) or None,
                status=status,
                published_at=row["post_date"] if row["post_date"] else None,
            )

            self.db.add(product)
            self.stats["products"] += 1

        self.db.commit()
        print(f"   ✅ Products: {self.stats['products']}")

    def _create_redirects(self):
        """Create redirects from old WordPress URLs to new ones."""
        # Common WP URL patterns → Z-Core patterns
        # /?p=123 → /blog/slug
        # /category/name/ → /shop?category=name
        # /product/name/ → /product/name
        print(f"   ℹ️  Redirects: Manual review recommended for SEO preservation")


# ── CLI ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Z-Core WordPress Migration Engine")
    parser.add_argument("--source", choices=["mysql", "xml"], required=True,
                        help="Migration source: mysql or xml")
    parser.add_argument("--file", help="Path to WordPress XML export file")
    parser.add_argument("--host", default="localhost", help="MySQL host")
    parser.add_argument("--port", type=int, default=3306, help="MySQL port")
    parser.add_argument("--db", help="MySQL database name")
    parser.add_argument("--user", help="MySQL user")
    parser.add_argument("--pass", dest="password", help="MySQL password")
    parser.add_argument("--prefix", default="wp_", help="WordPress table prefix")

    args = parser.parse_args()

    # Initialize database
    init_db()
    print("🚀 Z-Core Migration Engine")
    print("=" * 50)

    if args.source == "xml":
        if not args.file:
            print("❌ --file required for XML source")
            sys.exit(1)
        importer = WordPressXMLImporter(args.file)
        stats = importer.parse()
    else:
        if not all([args.db, args.user]):
            print("❌ --db and --user required for MySQL source")
            sys.exit(1)
        importer = WordPressMySQLImporter(
            args.host, args.port, args.db, args.user, args.password, args.prefix
        )
        stats = importer.migrate()

    print("\n" + "=" * 50)
    print("📊 Migration Complete!")
    for key, val in stats.items():
        if key != "errors":
            print(f"   {key}: {val}")
    if stats.get("errors"):
        print(f"\n⚠️  Errors ({len(stats['errors'])}):")
        for err in stats["errors"][:10]:
            print(f"   - {err}")


if __name__ == "__main__":
    main()
