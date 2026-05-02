"""
Z-Core API Routes
=================
JSON API for cart operations, product search, etc.
"""

import json
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import desc

from app.models.database import (
    get_db, Product, ProductVariant, Category, Post, PostStatus, ProductStatus
)

router = APIRouter()


@router.get("/products")
async def api_products(
    page: int = 1,
    per_page: int = 12,
    category: str = "",
    sort: str = "newest",
    q: str = "",
    db: DBSession = Depends(get_db)
):
    """Product listing API."""
    offset = (page - 1) * per_page
    query = db.query(Product).filter(Product.status == ProductStatus.PUBLISHED)

    if category:
        cat = db.query(Category).filter(Category.slug == category).first()
        if cat:
            query = query.filter(Product.categories.contains(cat))

    if q:
        query = query.filter(Product.name.like(f"%{q}%"))

    if sort == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price.desc())
    else:
        query = query.order_by(desc(Product.published_at))

    total = query.count()
    products = query.offset(offset).limit(per_page).all()

    return JSONResponse({
        "total": total,
        "page": page,
        "per_page": per_page,
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "slug": p.slug,
                "price": p.price,
                "sale_price": p.sale_price,
                "image": p.featured_image,
                "stock_status": p.stock_status,
            }
            for p in products
        ]
    })


@router.get("/products/{product_id}")
async def api_product_detail(product_id: int, db: DBSession = Depends(get_db)):
    """Product detail with variants."""
    product = db.query(Product).get(product_id)
    if not product or product.status != ProductStatus.PUBLISHED:
        return JSONResponse({"error": "Not found"}, status_code=404)

    variants = [
        {
            "id": v.id,
            "sku": v.sku,
            "name": v.name,
            "price": v.price,
            "sale_price": v.sale_price,
            "stock_status": v.stock_status,
            "stock_quantity": v.stock_quantity,
            "attributes": [
                {"name": va.attribute_name, "value": va.attribute_value}
                for va in v.attribute_values
            ]
        }
        for v in product.variants if v.is_active
    ]

    attributes = [
        {
            "name": a.name,
            "values": json.loads(a.values) if a.values else [],
            "is_variation": a.is_variation,
        }
        for a in product.attributes
    ]

    return JSONResponse({
        "id": product.id,
        "name": product.name,
        "slug": product.slug,
        "sku": product.sku,
        "description": product.description,
        "short_description": product.short_description,
        "price": product.price,
        "sale_price": product.sale_price,
        "stock_status": product.stock_status,
        "stock_quantity": product.stock_quantity,
        "image": product.featured_image,
        "gallery": json.loads(product.gallery_images) if product.gallery_images else [],
        "variants": variants,
        "attributes": attributes,
    })


@router.get("/search")
async def api_search(q: str = "", db: DBSession = Depends(get_db)):
    """Search API for autocomplete."""
    if not q or len(q) < 2:
        return JSONResponse({"results": []})

    pattern = f"%{q}%"
    products = db.query(Product).filter(
        Product.status == ProductStatus.PUBLISHED,
        Product.name.like(pattern)
    ).limit(5).all()

    posts = db.query(Post).filter(
        Post.status == PostStatus.PUBLISHED,
        Post.title.like(pattern)
    ).limit(5).all()

    return JSONResponse({
        "results": [
            {"type": "product", "title": p.name, "url": f"/product/{p.slug}", "image": p.featured_image}
            for p in products
        ] + [
            {"type": "post", "title": p.title, "url": f"/blog/{p.slug}"}
            for p in posts
        ]
    })
