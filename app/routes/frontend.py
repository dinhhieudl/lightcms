"""
Z-Core Frontend Routes
======================
Public-facing pages: homepage, blog, products, cart, checkout, pages.
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import desc

from app.models.database import (
    get_db, Post, Page, Product, ProductVariant, Category, Tag,
    Order, OrderItem, PostStatus, ProductStatus, OrderStatus
)
from app.core.templates import get_template_env
from app.utils.seo import build_meta_tags
from config import settings

router = APIRouter()
templates = get_template_env()


def get_front_template(name: str):
    return templates.get_template(f"front/{name}")


# ── Homepage ───────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def homepage(request: Request, db: DBSession = Depends(get_db)):
    # Check if a page is set as homepage
    home_page = db.query(Page).filter(Page.is_homepage == True, Page.status == PostStatus.PUBLISHED).first()
    if home_page:
        meta = build_meta_tags(
            title=home_page.meta_title or home_page.title,
            description=home_page.meta_description,
            site_title=settings.SITE_TITLE,
            site_url=settings.SITE_URL,
        )
        tmpl = get_front_template("page.html")
        return tmpl.render(request=request, page=home_page, meta=meta)

    # Default homepage: featured products + recent posts
    featured_products = db.query(Product).filter(
        Product.is_featured == True, Product.status == ProductStatus.PUBLISHED
    ).limit(8).all()

    recent_posts = db.query(Post).filter(
        Post.status == PostStatus.PUBLISHED
    ).order_by(desc(Post.published_at)).limit(6).all()

    categories = db.query(Category).filter(Category.parent_id == None).order_by(Category.sort_order).all()

    meta = build_meta_tags(
        title=settings.SITE_TITLE,
        description=settings.SITE_DESCRIPTION,
        site_title=settings.SITE_TITLE,
        site_url=settings.SITE_URL,
    )

    tmpl = get_front_template("home.html")
    return tmpl.render(
        request=request, meta=meta,
        featured_products=featured_products,
        recent_posts=recent_posts,
        categories=categories,
    )


# ── Blog ───────────────────────────────────────────────────────────────

@router.get("/blog", response_class=HTMLResponse)
async def blog_list(request: Request, page: int = 1, db: DBSession = Depends(get_db)):
    per_page = 12
    offset = (page - 1) * per_page

    total = db.query(Post).filter(Post.status == PostStatus.PUBLISHED).count()
    posts = db.query(Post).filter(
        Post.status == PostStatus.PUBLISHED
    ).order_by(desc(Post.published_at)).offset(offset).limit(per_page).all()

    total_pages = (total + per_page - 1) // per_page

    meta = build_meta_tags(
        title="Blog",
        site_title=settings.SITE_TITLE,
        site_url=settings.SITE_URL,
    )

    tmpl = get_front_template("blog.html")
    return tmpl.render(
        request=request, posts=posts, meta=meta,
        page=page, total_pages=total_pages, total=total,
    )


@router.get("/blog/{slug}", response_class=HTMLResponse)
async def blog_post(request: Request, slug: str, db: DBSession = Depends(get_db)):
    post = db.query(Post).filter(
        Post.slug == slug, Post.status == PostStatus.PUBLISHED
    ).first()
    if not post:
        tmpl = get_front_template("404.html")
        return HTMLResponse(tmpl.render(request=request), status_code=404)

    # Increment view count
    post.view_count += 1
    db.commit()

    meta = build_meta_tags(
        title=post.meta_title or post.title,
        description=post.meta_description or post.excerpt,
        og_image=post.og_image or post.featured_image,
        canonical=f"{settings.SITE_URL}/blog/{post.slug}",
        site_title=settings.SITE_TITLE,
        site_url=settings.SITE_URL,
    )

    # Related posts
    related = db.query(Post).filter(
        Post.status == PostStatus.PUBLISHED, Post.id != post.id
    ).order_by(desc(Post.published_at)).limit(3).all()

    tmpl = get_front_template("post.html")
    return tmpl.render(request=request, post=post, meta=meta, related=related)


# ── Products ───────────────────────────────────────────────────────────

@router.get("/shop", response_class=HTMLResponse)
async def shop_list(
    request: Request,
    page: int = 1,
    category: str = "",
    sort: str = "newest",
    db: DBSession = Depends(get_db)
):
    per_page = 12
    offset = (page - 1) * per_page

    query = db.query(Product).filter(Product.status == ProductStatus.PUBLISHED)

    if category:
        cat = db.query(Category).filter(Category.slug == category).first()
        if cat:
            query = query.filter(Product.categories.contains(cat))

    # Sorting
    if sort == "price_asc":
        query = query.order_by(Product.price.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price.desc())
    elif sort == "popular":
        query = query.order_by(Product.sales_count.desc())
    else:
        query = query.order_by(desc(Product.published_at))

    total = query.count()
    products = query.offset(offset).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page
    categories = db.query(Category).filter(Category.parent_id == None).order_by(Category.sort_order).all()

    meta = build_meta_tags(
        title="Sản phẩm" if not category else f"Danh mục: {category}",
        site_title=settings.SITE_TITLE,
        site_url=settings.SITE_URL,
    )

    tmpl = get_front_template("shop.html")
    return tmpl.render(
        request=request, products=products, meta=meta,
        page=page, total_pages=total_pages, total=total,
        categories=categories, current_category=category, current_sort=sort,
    )


@router.get("/product/{slug}", response_class=HTMLResponse)
async def product_detail(request: Request, slug: str, db: DBSession = Depends(get_db)):
    product = db.query(Product).filter(
        Product.slug == slug, Product.status == ProductStatus.PUBLISHED
    ).first()
    if not product:
        tmpl = get_front_template("404.html")
        return HTMLResponse(tmpl.render(request=request), status_code=404)

    product.view_count += 1
    db.commit()

    meta = build_meta_tags(
        title=product.meta_title or product.name,
        description=product.meta_description or product.short_description,
        og_image=product.og_image or product.featured_image,
        canonical=f"{settings.SITE_URL}/product/{product.slug}",
        site_title=settings.SITE_TITLE,
        site_url=settings.SITE_URL,
    )

    # Gallery images
    gallery = []
    if product.gallery_images:
        try:
            gallery = json.loads(product.gallery_images)
        except json.JSONDecodeError:
            pass

    # Related products
    related = db.query(Product).filter(
        Product.status == ProductStatus.PUBLISHED, Product.id != product.id
    ).order_by(desc(Product.published_at)).limit(4).all()

    tmpl = get_front_template("product.html")
    return tmpl.render(
        request=request, product=product, meta=meta,
        gallery=gallery, related=related,
    )


# ── Static Pages ───────────────────────────────────────────────────────

@router.get("/{slug}", response_class=HTMLResponse)
async def static_page(request: Request, slug: str, db: DBSession = Depends(get_db)):
    page = db.query(Page).filter(
        Page.slug == slug, Page.status == PostStatus.PUBLISHED
    ).first()
    if not page:
        tmpl = get_front_template("404.html")
        return HTMLResponse(tmpl.render(request=request), status_code=404)

    meta = build_meta_tags(
        title=page.meta_title or page.title,
        description=page.meta_description,
        site_title=settings.SITE_TITLE,
        site_url=settings.SITE_URL,
    )

    tmpl = get_front_template("page.html")
    return tmpl.render(request=request, page=page, meta=meta)


# ── Cart & Checkout ────────────────────────────────────────────────────

@router.get("/cart", response_class=HTMLResponse)
async def cart_page(request: Request):
    meta = build_meta_tags(title="Giỏ hàng", site_title=settings.SITE_TITLE, site_url=settings.SITE_URL)
    tmpl = get_front_template("cart.html")
    return tmpl.render(request=request, meta=meta)


@router.get("/checkout", response_class=HTMLResponse)
async def checkout_page(request: Request):
    meta = build_meta_tags(title="Thanh toán", site_title=settings.SITE_TITLE, site_url=settings.SITE_URL)
    tmpl = get_front_template("checkout.html")
    return tmpl.render(request=request, meta=meta)


@router.post("/checkout")
async def checkout_submit(
    request: Request,
    customer_name: str = Form(...),
    customer_email: str = Form(...),
    customer_phone: str = Form(...),
    shipping_address: str = Form(...),
    shipping_city: str = Form(""),
    shipping_district: str = Form(""),
    shipping_ward: str = Form(""),
    shipping_note: str = Form(""),
    payment_method: str = Form("cod"),
    cart_data: str = Form("[]"),
    db: DBSession = Depends(get_db)
):
    """Process checkout form submission."""
    import uuid

    try:
        cart_items = json.loads(cart_data)
    except json.JSONDecodeError:
        return RedirectResponse(url="/cart?error=invalid", status_code=302)

    if not cart_items:
        return RedirectResponse(url="/cart?error=empty", status_code=302)

    # Generate order number
    order_number = f"ZC-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    # Calculate totals
    subtotal = 0
    order_items = []
    for item in cart_items:
        product = db.query(Product).get(item.get("product_id"))
        if not product:
            continue
        variant = None
        if item.get("variant_id"):
            variant = db.query(ProductVariant).get(item["variant_id"])

        price = variant.price if variant and variant.price else product.price
        qty = int(item.get("quantity", 1))
        item_subtotal = price * qty
        subtotal += item_subtotal

        order_items.append(OrderItem(
            product_id=product.id,
            variant_id=variant.id if variant else None,
            product_name=product.name,
            product_sku=product.sku or "",
            variant_name=variant.name if variant else "",
            price=price,
            quantity=qty,
            subtotal=item_subtotal,
        ))

    total = subtotal  # Add shipping fee logic here if needed

    order = Order(
        order_number=order_number,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        shipping_address=shipping_address,
        shipping_city=shipping_city,
        shipping_district=shipping_district,
        shipping_ward=shipping_ward,
        shipping_note=shipping_note,
        payment_method=payment_method,
        subtotal=subtotal,
        total=total,
        items=order_items,
    )

    db.add(order)
    db.commit()

    # Send notifications
    from app.services.notification import notify_new_order
    import asyncio
    try:
        asyncio.create_task(notify_new_order(order, db))
    except Exception:
        pass  # Don't fail checkout on notification error

    # Update stock
    for oi in order_items:
        if oi.product_id:
            p = db.query(Product).get(oi.product_id)
            if p and p.manage_stock:
                p.stock_quantity = max(0, p.stock_quantity - oi.quantity)
                if p.stock_quantity == 0:
                    p.stock_status = "outofstock"
    db.commit()

    return RedirectResponse(url=f"/order-success?order={order_number}", status_code=302)


@router.get("/order-success", response_class=HTMLResponse)
async def order_success(request: Request, order: str = ""):
    meta = build_meta_tags(title="Đặt hàng thành công", site_title=settings.SITE_TITLE, site_url=settings.SITE_URL)
    tmpl = get_front_template("order_success.html")
    return tmpl.render(request=request, meta=meta, order_number=order)


# ── Search ─────────────────────────────────────────────────────────────

@router.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = "", db: DBSession = Depends(get_db)):
    results = {"posts": [], "products": []}
    if q and len(q) >= 2:
        pattern = f"%{q}%"
        results["posts"] = db.query(Post).filter(
            Post.status == PostStatus.PUBLISHED,
            (Post.title.like(pattern)) | (Post.content.like(pattern))
        ).limit(10).all()
        results["products"] = db.query(Product).filter(
            Product.status == ProductStatus.PUBLISHED,
            (Product.name.like(pattern)) | (Product.description.like(pattern))
        ).limit(10).all()

    meta = build_meta_tags(title=f"Tìm kiếm: {q}", site_title=settings.SITE_TITLE, site_url=settings.SITE_URL)
    tmpl = get_front_template("search.html")
    return tmpl.render(request=request, meta=meta, query=q, results=results)
