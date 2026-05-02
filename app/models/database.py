"""
Z-Core Database Schema
======================
SQLite ORM via SQLAlchemy. Maps WordPress/WooCommerce concepts
into a clean, normalized relational model.

Tables:
  users          ← wp_users
  user_meta      ← wp_usermeta
  categories     ← wp_terms + wp_term_taxonomy (hierarchical)
  tags           ← wp_terms + wp_term_taxonomy (flat)
  posts          ← wp_posts (post_type=post)
  pages          ← wp_posts (post_type=page)
  products       ← wp_posts + wp_postmeta (WooCommerce)
  product_variants ← wp_postmeta variations
  post_meta      ← wp_postmeta (generic key-value)
  media          ← wp_posts (post_type=attachment)
  orders         ← custom (replaces WooCommerce orders)
  order_items    ← custom
  options        ← wp_options
  redirects      ← SEO redirect mapping
  seo_meta       ← extracted SEO metadata
"""

from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Float,
    Boolean, DateTime, ForeignKey, Index, Enum as SAEnum,
    event
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.pool import StaticPool
import enum
import os

Base = declarative_base()


# ── Enums ──────────────────────────────────────────────────────────────

class PostStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    PENDING = "pending"
    TRASH = "trash"


class ProductStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    PENDING = "pending"
    TRASH = "trash"


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    AUTHOR = "author"
    CUSTOMER = "customer"


# ── Users ──────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(60), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), default="")
    first_name = Column(String(100), default="")
    last_name = Column(String(100), default="")
    role = Column(SAEnum(UserRole), default=UserRole.CUSTOMER)
    avatar_url = Column(String(500), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    posts = relationship("Post", back_populates="author")
    orders = relationship("Order", back_populates="customer")
    meta = relationship("UserMeta", back_populates="user", cascade="all, delete-orphan")


class UserMeta(Base):
    __tablename__ = "user_meta"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    meta_key = Column(String(255), nullable=False)
    meta_value = Column(Text, default="")

    user = relationship("User", back_populates="meta")

    __table_args__ = (
        Index("ix_user_meta_key", "user_id", "meta_key"),
    )


# ── Taxonomy ───────────────────────────────────────────────────────────

class Category(Base):
    """Hierarchical taxonomy (like WordPress categories)."""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    parent_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    image_url = Column(String(500), default="")
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Self-referential hierarchy
    parent = relationship("Category", remote_side=[id], backref="children")
    posts = relationship("Post", secondary="post_categories", back_populates="categories")
    products = relationship("Product", secondary="product_categories", back_populates="categories")


class Tag(Base):
    """Flat taxonomy (like WordPress tags)."""
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    posts = relationship("Post", secondary="post_tags", back_populates="tags")
    products = relationship("Product", secondary="product_tags", back_populates="tags")


# ── Junction Tables ────────────────────────────────────────────────────

from sqlalchemy import Table

post_categories = Table(
    "post_categories", Base.metadata,
    Column("post_id", Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)

post_tags = Table(
    "post_tags", Base.metadata,
    Column("post_id", Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

product_categories = Table(
    "product_categories", Base.metadata,
    Column("product_id", Integer, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)

product_tags = Table(
    "product_tags", Base.metadata,
    Column("product_id", Integer, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


# ── Posts ──────────────────────────────────────────────────────────────

class Post(Base):
    """Blog posts and articles."""
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    slug = Column(String(500), unique=True, nullable=False, index=True)
    content = Column(Text, default="")  # Markdown
    excerpt = Column(Text, default="")
    featured_image = Column(String(500), default="")
    status = Column(SAEnum(PostStatus), default=PostStatus.DRAFT)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    template = Column(String(100), default="post")  # Jinja2 template override
    is_sticky = Column(Boolean, default=False)
    view_count = Column(Integer, default=0)

    # SEO fields (inline — no separate table needed)
    meta_title = Column(String(200), default="")
    meta_description = Column(String(500), default="")
    canonical_url = Column(String(500), default="")
    og_image = Column(String(500), default="")

    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    author = relationship("User", back_populates="posts")
    categories = relationship("Category", secondary="post_categories", back_populates="posts")
    tags = relationship("Tag", secondary="post_tags", back_populates="posts")
    meta = relationship("PostMeta", back_populates="post", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_posts_status_published", "status", "published_at"),
    )


class PostMeta(Base):
    """Generic key-value metadata for posts."""
    __tablename__ = "post_meta"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    meta_key = Column(String(255), nullable=False)
    meta_value = Column(Text, default="")

    post = relationship("Post", back_populates="meta")

    __table_args__ = (
        Index("ix_post_meta_key", "post_id", "meta_key"),
    )


# ── Pages ──────────────────────────────────────────────────────────────

class Page(Base):
    """Static pages (About, Contact, etc.)."""
    __tablename__ = "pages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    slug = Column(String(500), unique=True, nullable=False, index=True)
    content = Column(Text, default="")  # Markdown
    template = Column(String(100), default="page")  # Jinja2 template override
    parent_id = Column(Integer, ForeignKey("pages.id", ondelete="SET NULL"), nullable=True)
    sort_order = Column(Integer, default=0)
    status = Column(SAEnum(PostStatus), default=PostStatus.DRAFT)
    is_homepage = Column(Boolean, default=False)

    # SEO fields
    meta_title = Column(String(200), default="")
    meta_description = Column(String(500), default="")
    canonical_url = Column(String(500), default="")
    og_image = Column(String(500), default="")

    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    parent = relationship("Page", remote_side=[id], backref="children")


# ── Products (WooCommerce) ────────────────────────────────────────────

class Product(Base):
    """E-commerce product, replaces WooCommerce product."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(500), nullable=False)
    slug = Column(String(500), unique=True, nullable=False, index=True)
    sku = Column(String(100), unique=True, nullable=True, index=True)
    description = Column(Text, default="")  # Markdown
    short_description = Column(Text, default="")

    # Pricing
    price = Column(Float, default=0.0)
    sale_price = Column(Float, nullable=True)
    cost_price = Column(Float, nullable=True)  # For profit tracking
    currency = Column(String(3), default="VND")

    # Inventory
    stock_quantity = Column(Integer, default=0)
    stock_status = Column(String(20), default="instock")  # instock, outofstock, onbackorder
    manage_stock = Column(Boolean, default=False)
    low_stock_threshold = Column(Integer, default=5)

    # Physical attributes
    weight = Column(Float, nullable=True)
    length = Column(Float, nullable=True)
    width = Column(Float, nullable=True)
    height = Column(Float, nullable=True)

    # Product type
    product_type = Column(String(20), default="simple")  # simple, variable, grouped, digital
    is_virtual = Column(Boolean, default=False)
    is_downloadable = Column(Boolean, default=False)
    download_url = Column(String(500), default="")

    # Status & visibility
    status = Column(SAEnum(ProductStatus), default=ProductStatus.DRAFT)
    is_featured = Column(Boolean, default=False)
    featured_image = Column(String(500), default="")
    gallery_images = Column(Text, default="")  # JSON array of image URLs

    # SEO
    meta_title = Column(String(200), default="")
    meta_description = Column(String(500), default="")
    canonical_url = Column(String(500), default="")
    og_image = Column(String(500), default="")

    # Stats
    view_count = Column(Integer, default=0)
    sales_count = Column(Integer, default=0)
    rating_avg = Column(Float, default=0.0)
    rating_count = Column(Integer, default=0)

    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    categories = relationship("Category", secondary="product_categories", back_populates="products")
    tags = relationship("Tag", secondary="product_tags", back_populates="products")
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    attributes = relationship("ProductAttribute", back_populates="product", cascade="all, delete-orphan")
    meta = relationship("ProductMeta", back_populates="product", cascade="all, delete-orphan")
    order_items = relationship("OrderItem", back_populates="product")

    __table_args__ = (
        Index("ix_products_status_featured", "status", "is_featured"),
        Index("ix_products_price", "price"),
    )


class ProductVariant(Base):
    """Product variations (size, color, etc.)."""
    __tablename__ = "product_variants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    sku = Column(String(100), unique=True, nullable=True, index=True)
    name = Column(String(500), default="")  # e.g. "Red / XL"
    price = Column(Float, nullable=True)  # Override parent price if set
    sale_price = Column(Float, nullable=True)
    stock_quantity = Column(Integer, default=0)
    stock_status = Column(String(20), default="instock")
    image_url = Column(String(500), default="")
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="variants")
    attribute_values = relationship("VariantAttributeValue", back_populates="variant",
                                    cascade="all, delete-orphan")


class ProductAttribute(Base):
    """Attribute definitions for variable products (e.g., Color, Size)."""
    __tablename__ = "product_attributes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)  # e.g. "Color"
    values = Column(Text, default="")  # JSON array: ["Red","Blue","Green"]
    is_variation = Column(Boolean, default=True)  # Used for creating variants?
    sort_order = Column(Integer, default=0)

    product = relationship("Product", back_populates="attributes")


class VariantAttributeValue(Base):
    """Links a variant to specific attribute values."""
    __tablename__ = "variant_attribute_values"

    id = Column(Integer, primary_key=True, autoincrement=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="CASCADE"), nullable=False, index=True)
    attribute_name = Column(String(100), nullable=False)
    attribute_value = Column(String(200), nullable=False)

    variant = relationship("ProductVariant", back_populates="attribute_values")

    __table_args__ = (
        Index("ix_variant_attr", "variant_id", "attribute_name"),
    )


class ProductMeta(Base):
    """Generic key-value metadata for products."""
    __tablename__ = "product_meta"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    meta_key = Column(String(255), nullable=False)
    meta_value = Column(Text, default="")

    product = relationship("Product", back_populates="meta")

    __table_args__ = (
        Index("ix_product_meta_key", "product_id", "meta_key"),
    )


# ── Orders ─────────────────────────────────────────────────────────────

class Order(Base):
    """Customer orders, replaces WooCommerce orders."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_number = Column(String(50), unique=True, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(SAEnum(OrderStatus), default=OrderStatus.PENDING)

    # Customer info (snapshot at order time)
    customer_name = Column(String(200), default="")
    customer_email = Column(String(200), default="")
    customer_phone = Column(String(50), default="")

    # Shipping address
    shipping_address = Column(Text, default="")
    shipping_city = Column(String(100), default="")
    shipping_district = Column(String(100), default="")
    shipping_ward = Column(String(100), default="")
    shipping_note = Column(Text, default="")

    # Totals
    subtotal = Column(Float, default=0.0)
    shipping_fee = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    currency = Column(String(3), default="VND")

    # Payment
    payment_method = Column(String(50), default="cod")  # cod, bank_transfer, etc.
    payment_status = Column(String(20), default="pending")  # pending, paid, failed, refunded
    transaction_id = Column(String(200), default="")

    # Fulfillment
    tracking_number = Column(String(200), default="")
    shipping_provider = Column(String(100), default="")

    # Notes
    admin_note = Column(Text, default="")
    customer_note = Column(Text, default="")

    # Notification tracking
    telegram_notified = Column(Boolean, default=False)
    email_notified = Column(Boolean, default=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    customer = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    """Individual items within an order."""
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=True)

    # Snapshot at order time (product may change/delete later)
    product_name = Column(String(500), nullable=False)
    product_sku = Column(String(100), default="")
    variant_name = Column(String(500), default="")
    price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    subtotal = Column(Float, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


# ── Media ──────────────────────────────────────────────────────────────

class Media(Base):
    """Uploaded media files (images, documents)."""
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), default="")
    file_path = Column(String(1000), nullable=False)  # Relative to uploads dir
    file_size = Column(Integer, default=0)
    mime_type = Column(String(100), default="")
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    alt_text = Column(String(500), default="")
    title = Column(String(500), default="")
    caption = Column(Text, default="")

    # WebP conversion
    webp_path = Column(String(1000), default="")
    original_path = Column(String(1000), default="")  # Before conversion

    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Site Options ───────────────────────────────────────────────────────

class Option(Base):
    """Site-wide configuration, replaces wp_options."""
    __tablename__ = "options"

    id = Column(Integer, primary_key=True, autoincrement=True)
    option_key = Column(String(255), unique=True, nullable=False, index=True)
    option_value = Column(Text, default="")
    autoload = Column(Boolean, default=True)


# ── Redirects (SEO) ───────────────────────────────────────────────────

class Redirect(Base):
    """URL redirects for SEO preservation during migration."""
    __tablename__ = "redirects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_url = Column(String(1000), nullable=False, unique=True, index=True)
    to_url = Column(String(1000), nullable=False)
    status_code = Column(Integer, default=301)  # 301 or 302
    hit_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Sessions (Admin auth) ─────────────────────────────────────────────

class Session(Base):
    """Admin session store."""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_key = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    data = Column(Text, default="{}")
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Database Engine & Session Factory ─────────────────────────────────

_db_path = os.environ.get("ZCORE_DB_PATH", "data/zcore.db")
_engine = None
_SessionLocal = None


def get_engine(global_engine=False):
    global _engine
    if _engine is None:
        os.makedirs(os.path.dirname(_db_path) if os.path.dirname(_db_path) else ".", exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{_db_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )
        # Enable WAL mode for better concurrent read performance
        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()
    return _engine


def get_session():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()


def init_db():
    """Create all tables."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


def get_db():
    """FastAPI dependency — yields a DB session."""
    db = get_session()
    try:
        yield db
    finally:
        db.close()
