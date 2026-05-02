"""
Z-Core Template Engine
======================
Jinja2 setup with custom filters and global context.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from config import settings


def slugify(text: str) -> str:
    """Simple slugify for Vietnamese + English."""
    import unicodedata
    import re
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text


def format_price(amount: float, currency: str = "VND") -> str:
    """Format price with thousand separators."""
    if currency == "VND":
        return f"{int(amount):,}".replace(",", ".") + "₫"
    return f"{amount:,.2f} {currency}"


def timeago(dt: datetime) -> str:
    """Human-readable time ago."""
    if not dt:
        return ""
    now = datetime.utcnow()
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "vừa xong"
    elif seconds < 3600:
        return f"{seconds // 60} phút trước"
    elif seconds < 86400:
        return f"{seconds // 3600} giờ trước"
    elif seconds < 2592000:
        return f"{seconds // 86400} ngày trước"
    else:
        return dt.strftime("%d/%m/%Y")


def truncate_html(text: str, length: int = 160) -> str:
    """Truncate text (strips HTML)."""
    import re
    clean = re.sub(r"<[^>]+>", "", text)
    if len(clean) <= length:
        return clean
    return clean[:length].rsplit(" ", 1)[0] + "…"


def markdown_to_html(text: str) -> str:
    """Convert Markdown to HTML."""
    try:
        import markdown
        return markdown.markdown(text, extensions=["extra", "codehilite", "toc"])
    except ImportError:
        # Fallback: return as-is if markdown not installed
        return text.replace("\n", "<br>")


def json_filter(value) -> str:
    """JSON serialization filter."""
    return json.dumps(value, ensure_ascii=False)


def get_template_env() -> Environment:
    """Create and configure Jinja2 environment."""
    env = Environment(
        loader=FileSystemLoader(str(settings.TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Custom filters
    env.filters["slugify"] = slugify
    env.filters["format_price"] = format_price
    env.filters["timeago"] = timeago
    env.filters["truncate_html"] = truncate_html
    env.filters["markdown"] = markdown_to_html
    env.filters["tojson"] = json_filter

    # Global context
    env.globals.update({
        "site_url": settings.SITE_URL,
        "site_title": settings.SITE_TITLE,
        "site_description": settings.SITE_DESCRIPTION,
        "site_language": settings.SITE_LANGUAGE,
        "admin_prefix": settings.ADMIN_PREFIX,
        "app_version": settings.APP_VERSION,
        "now": datetime.utcnow(),
    })

    return env
