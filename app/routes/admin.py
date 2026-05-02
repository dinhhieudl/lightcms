"""
Z-Core Admin Routes
===================
Minimal admin panel for managing posts, pages, products, orders.
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Depends, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import desc

from app.models.database import (
    get_db, User, Post, Page, Product, ProductVariant, ProductAttribute,
    Category, Tag, Order, Media, Redirect, Option,
    PostStatus, ProductStatus, OrderStatus
)
from app.core.security import verify_password, create_session, destroy_session, hash_password
from app.core.templates import get_template_env, slugify
from config import settings

router = APIRouter()
templates = get_template_env()


def get_admin_template(name: str):
    return templates.get_template(f"admin/{name}")


# ── Auth ───────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    tmpl = get_admin_template("login.html")
    return tmpl.render(request=request, error="")


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: DBSession = Depends(get_db)
):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        tmpl = get_admin_template("login.html")
        return tmpl.render(request=request, error="Sai tài khoản hoặc mật khẩu")

    session_key = create_session(db, user.id)
    next_url = request.query_params.get("next", f"{settings.ADMIN_PREFIX}/")
    response = RedirectResponse(url=next_url, status_code=302)
    response.set_cookie("zcore_session", session_key, httponly=True, max_age=settings.SESSION_MAX_AGE)
    return response


@router.get("/logout")
async def logout(request: Request, db: DBSession = Depends(get_db)):
    session_key = request.cookies.get("zcore_session")
    if session_key:
        destroy_session(db, session_key)
    response = RedirectResponse(url=f"{settings.ADMIN_PREFIX}/login", status_code=302)
    response.delete_cookie("zcore_session")
    return response


# ── Dashboard ──────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: DBSession = Depends(get_db)):
    stats = {
        "posts": db.query(Post).count(),
        "pages": db.query(Page).count(),
        "products": db.query(Product).count(),
        "orders": db.query(Order).count(),
        "pending_orders": db.query(Order).filter(Order.status == OrderStatus.PENDING).count(),
        "categories": db.query(Category).count(),
    }
    recent_orders = db.query(Order).order_by(desc(Order.created_at)).limit(5).all()
    recent_posts = db.query(Post).order_by(desc(Post.created_at)).limit(5).all()

    tmpl = get_admin_template("dashboard.html")
    return tmpl.render(request=request, stats=stats, recent_orders=recent_orders, recent_posts=recent_posts)


# ── Posts CRUD ─────────────────────────────────────────────────────────

@router.get("/posts", response_class=HTMLResponse)
async def posts_list(request: Request, db: DBSession = Depends(get_db)):
    posts = db.query(Post).order_by(desc(Post.created_at)).all()
    tmpl = get_admin_template("posts/list.html")
    return tmpl.render(request=request, posts=posts)


@router.get("/posts/new", response_class=HTMLResponse)
async def post_new(request: Request, db: DBSession = Depends(get_db)):
    categories = db.query(Category).all()
    tags = db.query(Tag).all()
    tmpl = get_admin_template("posts/edit.html")
    return tmpl.render(request=request, post=None, categories=categories, tags=tags)


@router.post("/posts/new")
async def post_create(
    request: Request,
    title: str = Form(...),
    content: str = Form(""),
    excerpt: str = Form(""),
    status: str = Form("draft"),
    category_ids: str = Form(""),
    tag_ids: str = Form(""),
    meta_title: str = Form(""),
    meta_description: str = Form(""),
    featured_image: UploadFile = File(None),
    db: DBSession = Depends(get_db)
):
    slug = slugify(title)
    # Ensure unique slug
    base_slug = slug
    counter = 1
    while db.query(Post).filter(Post.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    post = Post(
        title=title,
        slug=slug,
        content=content,
        excerpt=excerpt,
        status=PostStatus(status),
        author_id=request.state.user.id,
        meta_title=meta_title,
        meta_description=meta_description,
        published_at=datetime.now(timezone.utc) if status == "published" else None,
    )

    # Handle featured image
    if featured_image and featured_image.filename:
        from app.utils.image import get_upload_path, convert_to_webp
        file_path = get_upload_path(featured_image.filename, "posts")
        file_path.write_bytes(await featured_image.read())
        webp_path = convert_to_webp(str(file_path))
        post.featured_image = "/" + str(webp_path).replace(str(settings.STATIC_DIR) + "/", "")

    # Categories
    if category_ids:
        for cid in category_ids.split(","):
            cid = cid.strip()
            if cid.isdigit():
                cat = db.query(Category).get(int(cid))
                if cat:
                    post.categories.append(cat)

    # Tags
    if tag_ids:
        for tid in tag_ids.split(","):
            tid = tid.strip()
            if tid.isdigit():
                tag = db.query(Tag).get(int(tid))
                if tag:
                    post.tags.append(tag)

    db.add(post)
    db.commit()
    return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/posts", status_code=302)


@router.get("/posts/{post_id}/edit", response_class=HTMLResponse)
async def post_edit(request: Request, post_id: int, db: DBSession = Depends(get_db)):
    post = db.query(Post).get(post_id)
    if not post:
        return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/posts", status_code=302)
    categories = db.query(Category).all()
    tags = db.query(Tag).all()
    tmpl = get_admin_template("posts/edit.html")
    return tmpl.render(request=request, post=post, categories=categories, tags=tags)


@router.post("/posts/{post_id}/edit")
async def post_update(
    request: Request,
    post_id: int,
    title: str = Form(...),
    content: str = Form(""),
    excerpt: str = Form(""),
    status: str = Form("draft"),
    category_ids: str = Form(""),
    tag_ids: str = Form(""),
    meta_title: str = Form(""),
    meta_description: str = Form(""),
    featured_image: UploadFile = File(None),
    db: DBSession = Depends(get_db)
):
    post = db.query(Post).get(post_id)
    if not post:
        return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/posts", status_code=302)

    post.title = title
    post.content = content
    post.excerpt = excerpt
    post.status = PostStatus(status)
    post.meta_title = meta_title
    post.meta_description = meta_description

    if status == "published" and not post.published_at:
        post.published_at = datetime.now(timezone.utc)

    if featured_image and featured_image.filename:
        from app.utils.image import get_upload_path, convert_to_webp
        file_path = get_upload_path(featured_image.filename, "posts")
        file_path.write_bytes(await featured_image.read())
        webp_path = convert_to_webp(str(file_path))
        post.featured_image = "/" + str(webp_path).replace(str(settings.STATIC_DIR) + "/", "")

    # Update categories
    post.categories.clear()
    if category_ids:
        for cid in category_ids.split(","):
            cid = cid.strip()
            if cid.isdigit():
                cat = db.query(Category).get(int(cid))
                if cat:
                    post.categories.append(cat)

    # Update tags
    post.tags.clear()
    if tag_ids:
        for tid in tag_ids.split(","):
            tid = tid.strip()
            if tid.isdigit():
                tag = db.query(Tag).get(int(tid))
                if tag:
                    post.tags.append(tag)

    db.commit()
    return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/posts", status_code=302)


@router.get("/posts/{post_id}/delete")
async def post_delete(request: Request, post_id: int, db: DBSession = Depends(get_db)):
    post = db.query(Post).get(post_id)
    if post:
        db.delete(post)
        db.commit()
    return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/posts", status_code=302)


# ── Pages CRUD ─────────────────────────────────────────────────────────

@router.get("/pages", response_class=HTMLResponse)
async def pages_list(request: Request, db: DBSession = Depends(get_db)):
    pages = db.query(Page).order_by(Page.sort_order).all()
    tmpl = get_admin_template("pages/list.html")
    return tmpl.render(request=request, pages=pages)


@router.get("/pages/new", response_class=HTMLResponse)
async def page_new(request: Request):
    tmpl = get_admin_template("pages/edit.html")
    return tmpl.render(request=request, page=None)


@router.post("/pages/new")
async def page_create(
    request: Request,
    title: str = Form(...),
    content: str = Form(""),
    status: str = Form("draft"),
    template: str = Form("page"),
    meta_title: str = Form(""),
    meta_description: str = Form(""),
    db: DBSession = Depends(get_db)
):
    slug = slugify(title)
    base_slug = slug
    counter = 1
    while db.query(Page).filter(Page.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    page = Page(
        title=title,
        slug=slug,
        content=content,
        status=PostStatus(status),
        template=template,
        meta_title=meta_title,
        meta_description=meta_description,
        published_at=datetime.now(timezone.utc) if status == "published" else None,
    )
    db.add(page)
    db.commit()
    return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/pages", status_code=302)


@router.get("/pages/{page_id}/edit", response_class=HTMLResponse)
async def page_edit(request: Request, page_id: int, db: DBSession = Depends(get_db)):
    page = db.query(Page).get(page_id)
    if not page:
        return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/pages", status_code=302)
    tmpl = get_admin_template("pages/edit.html")
    return tmpl.render(request=request, page=page)


@router.post("/pages/{page_id}/edit")
async def page_update(
    request: Request,
    page_id: int,
    title: str = Form(...),
    content: str = Form(""),
    status: str = Form("draft"),
    template: str = Form("page"),
    meta_title: str = Form(""),
    meta_description: str = Form(""),
    db: DBSession = Depends(get_db)
):
    page = db.query(Page).get(page_id)
    if not page:
        return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/pages", status_code=302)

    page.title = title
    page.content = content
    page.status = PostStatus(status)
    page.template = template
    page.meta_title = meta_title
    page.meta_description = meta_description
    if status == "published" and not page.published_at:
        page.published_at = datetime.now(timezone.utc)
    db.commit()
    return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/pages", status_code=302)


@router.get("/pages/{page_id}/delete")
async def page_delete(request: Request, page_id: int, db: DBSession = Depends(get_db)):
    page = db.query(Page).get(page_id)
    if page:
        db.delete(page)
        db.commit()
    return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/pages", status_code=302)


# ── Products CRUD ──────────────────────────────────────────────────────

@router.get("/products", response_class=HTMLResponse)
async def products_list(request: Request, db: DBSession = Depends(get_db)):
    products = db.query(Product).order_by(desc(Product.created_at)).all()
    tmpl = get_admin_template("products/list.html")
    return tmpl.render(request=request, products=products)


@router.get("/products/new", response_class=HTMLResponse)
async def product_new(request: Request, db: DBSession = Depends(get_db)):
    categories = db.query(Category).all()
    tmpl = get_admin_template("products/edit.html")
    return tmpl.render(request=request, product=None, categories=categories)


@router.post("/products/new")
async def product_create(
    request: Request,
    name: str = Form(...),
    sku: str = Form(""),
    description: str = Form(""),
    short_description: str = Form(""),
    price: float = Form(0),
    sale_price: float = Form(None),
    stock_quantity: int = Form(0),
    stock_status: str = Form("instock"),
    product_type: str = Form("simple"),
    status: str = Form("draft"),
    category_ids: str = Form(""),
    featured_image: UploadFile = File(None),
    db: DBSession = Depends(get_db)
):
    slug = slugify(name)
    base_slug = slug
    counter = 1
    while db.query(Product).filter(Product.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    product = Product(
        name=name,
        slug=slug,
        sku=sku or None,
        description=description,
        short_description=short_description,
        price=price,
        sale_price=sale_price if sale_price else None,
        stock_quantity=stock_quantity,
        stock_status=stock_status,
        product_type=product_type,
        status=ProductStatus(status),
        published_at=datetime.now(timezone.utc) if status == "published" else None,
    )

    if featured_image and featured_image.filename:
        from app.utils.image import get_upload_path, convert_to_webp
        file_path = get_upload_path(featured_image.filename, "products")
        file_path.write_bytes(await featured_image.read())
        webp_path = convert_to_webp(str(file_path))
        product.featured_image = "/" + str(webp_path).replace(str(settings.STATIC_DIR) + "/", "")

    if category_ids:
        for cid in category_ids.split(","):
            cid = cid.strip()
            if cid.isdigit():
                cat = db.query(Category).get(int(cid))
                if cat:
                    product.categories.append(cat)

    db.add(product)
    db.commit()
    return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/products", status_code=302)


@router.get("/products/{product_id}/edit", response_class=HTMLResponse)
async def product_edit(request: Request, product_id: int, db: DBSession = Depends(get_db)):
    product = db.query(Product).get(product_id)
    if not product:
        return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/products", status_code=302)
    categories = db.query(Category).all()
    tmpl = get_admin_template("products/edit.html")
    return tmpl.render(request=request, product=product, categories=categories)


@router.post("/products/{product_id}/edit")
async def product_update(
    request: Request,
    product_id: int,
    name: str = Form(...),
    sku: str = Form(""),
    description: str = Form(""),
    short_description: str = Form(""),
    price: float = Form(0),
    sale_price: float = Form(None),
    stock_quantity: int = Form(0),
    stock_status: str = Form("instock"),
    product_type: str = Form("simple"),
    status: str = Form("draft"),
    category_ids: str = Form(""),
    featured_image: UploadFile = File(None),
    db: DBSession = Depends(get_db)
):
    product = db.query(Product).get(product_id)
    if not product:
        return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/products", status_code=302)

    product.name = name
    product.sku = sku or None
    product.description = description
    product.short_description = short_description
    product.price = price
    product.sale_price = sale_price if sale_price else None
    product.stock_quantity = stock_quantity
    product.stock_status = stock_status
    product.product_type = product_type
    product.status = ProductStatus(status)
    if status == "published" and not product.published_at:
        product.published_at = datetime.now(timezone.utc)

    if featured_image and featured_image.filename:
        from app.utils.image import get_upload_path, convert_to_webp
        file_path = get_upload_path(featured_image.filename, "products")
        file_path.write_bytes(await featured_image.read())
        webp_path = convert_to_webp(str(file_path))
        product.featured_image = "/" + str(webp_path).replace(str(settings.STATIC_DIR) + "/", "")

    product.categories.clear()
    if category_ids:
        for cid in category_ids.split(","):
            cid = cid.strip()
            if cid.isdigit():
                cat = db.query(Category).get(int(cid))
                if cat:
                    product.categories.append(cat)

    db.commit()
    return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/products", status_code=302)


@router.get("/products/{product_id}/delete")
async def product_delete(request: Request, product_id: int, db: DBSession = Depends(get_db)):
    product = db.query(Product).get(product_id)
    if product:
        db.delete(product)
        db.commit()
    return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/products", status_code=302)


# ── Orders ─────────────────────────────────────────────────────────────

@router.get("/orders", response_class=HTMLResponse)
async def orders_list(request: Request, status: str = "", db: DBSession = Depends(get_db)):
    query = db.query(Order)
    if status:
        query = query.filter(Order.status == OrderStatus(status))
    orders = query.order_by(desc(Order.created_at)).all()
    tmpl = get_admin_template("orders/list.html")
    return tmpl.render(request=request, orders=orders, current_status=status)


@router.get("/orders/{order_id}", response_class=HTMLResponse)
async def order_detail(request: Request, order_id: int, db: DBSession = Depends(get_db)):
    order = db.query(Order).get(order_id)
    if not order:
        return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/orders", status_code=302)
    tmpl = get_admin_template("orders/detail.html")
    return tmpl.render(request=request, order=order)


@router.post("/orders/{order_id}/status")
async def order_update_status(
    request: Request,
    order_id: int,
    status: str = Form(...),
    admin_note: str = Form(""),
    db: DBSession = Depends(get_db)
):
    order = db.query(Order).get(order_id)
    if order:
        order.status = OrderStatus(status)
        if admin_note:
            order.admin_note = admin_note
        db.commit()
    return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/orders/{order_id}", status_code=302)


# ── Categories ─────────────────────────────────────────────────────────

@router.get("/categories", response_class=HTMLResponse)
async def categories_list(request: Request, db: DBSession = Depends(get_db)):
    categories = db.query(Category).order_by(Category.sort_order).all()
    tmpl = get_admin_template("categories/list.html")
    return tmpl.render(request=request, categories=categories)


@router.post("/categories/new")
async def category_create(
    request: Request,
    name: str = Form(...),
    parent_id: int = Form(None),
    description: str = Form(""),
    db: DBSession = Depends(get_db)
):
    slug = slugify(name)
    cat = Category(name=name, slug=slug, description=description, parent_id=parent_id)
    db.add(cat)
    db.commit()
    return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/categories", status_code=302)


@router.get("/categories/{cat_id}/delete")
async def category_delete(request: Request, cat_id: int, db: DBSession = Depends(get_db)):
    cat = db.query(Category).get(cat_id)
    if cat:
        db.delete(cat)
        db.commit()
    return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/categories", status_code=302)


# ── Settings ───────────────────────────────────────────────────────────

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: DBSession = Depends(get_db)):
    options = {o.option_key: o.option_value for o in db.query(Option).all()}
    tmpl = get_admin_template("settings.html")
    return tmpl.render(request=request, options=options)


@router.post("/settings")
async def settings_save(request: Request, db: DBSession = Depends(get_db)):
    form = await request.form()
    for key, value in form.items():
        opt = db.query(Option).filter(Option.option_key == key).first()
        if opt:
            opt.option_value = str(value)
        else:
            db.add(Option(option_key=key, option_value=str(value)))
    db.commit()
    return RedirectResponse(url=f"{settings.ADMIN_PREFIX}/settings", status_code=302)
