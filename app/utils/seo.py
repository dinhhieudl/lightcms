"""
Z-Core SEO Utilities
====================
Auto-generate sitemap.xml, robots.txt, and meta tags.
"""

from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring
from typing import List, Dict


def generate_sitemap(pages: List[Dict], posts: List[Dict], products: List[Dict],
                     site_url: str) -> str:
    """
    Generate sitemap.xml content.

    Each item dict should have: {loc, lastmod, changefreq, priority}
    """
    urlset = Element("urlset")
    urlset.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")

    def add_url(loc: str, lastmod: str = "", changefreq: str = "weekly", priority: str = "0.5"):
        url_el = SubElement(urlset, "url")
        SubElement(url_el, "loc").text = f"{site_url}{loc}"
        if lastmod:
            SubElement(url_el, "lastmod").text = lastmod
        SubElement(url_el, "changefreq").text = changefreq
        SubElement(url_el, "priority").text = priority

    # Homepage
    add_url("/", changefreq="daily", priority="1.0")

    # Pages
    for page in pages:
        add_url(
            f"/{page['slug']}",
            lastmod=page.get("updated_at", ""),
            changefreq="monthly",
            priority="0.8"
        )

    # Posts
    for post in posts:
        date_str = post.get("published_at", post.get("created_at", ""))
        if isinstance(date_str, datetime):
            date_str = date_str.strftime("%Y-%m-%d")
        add_url(
            f"/blog/{post['slug']}",
            lastmod=date_str,
            changefreq="weekly",
            priority="0.6"
        )

    # Products
    for product in products:
        date_str = product.get("updated_at", product.get("created_at", ""))
        if isinstance(date_str, datetime):
            date_str = date_str.strftime("%Y-%m-%d")
        add_url(
            f"/product/{product['slug']}",
            lastmod=date_str,
            changefreq="weekly",
            priority="0.7"
        )

    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_str += tostring(urlset, encoding="unicode", xml_declaration=False)
    return xml_str


def generate_robots_txt(site_url: str) -> str:
    """Generate robots.txt content."""
    return f"""User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/

Sitemap: {site_url}/sitemap.xml
"""


def build_meta_tags(title: str = "", description: str = "", og_image: str = "",
                    canonical: str = "", site_title: str = "",
                    site_url: str = "") -> Dict[str, str]:
    """Build meta tag dictionary for templates."""
    full_title = f"{title} | {site_title}" if title and site_title else (title or site_title)

    tags = {
        "title": full_title,
        "description": description,
        "og:title": full_title,
        "og:description": description,
        "og:type": "website",
        "og:url": canonical or site_url,
        "twitter:card": "summary_large_image" if og_image else "summary",
    }

    if og_image:
        if not og_image.startswith("http"):
            og_image = f"{site_url}{og_image}"
        tags["og:image"] = og_image
        tags["twitter:image"] = og_image

    if canonical:
        tags["canonical"] = canonical

    return tags
