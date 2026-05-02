#!/usr/bin/env python3
"""
Z-Core Seed Script — Generate 1000 sample products + sample data for testing.
"""

import sys
import random
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.database import (
    init_db, get_session, get_engine, Base,
    User, Category, Tag, Post, Page, Product, ProductVariant,
    ProductAttribute, Order, OrderItem, Option,
    PostStatus, ProductStatus, OrderStatus, UserRole
)
from app.core.security import hash_password

# ── Sample Data ────────────────────────────────────────────────────────

CATEGORIES = [
    ("Điện thoại", "dien-thoai"),
    ("Laptop", "laptop"),
    ("Tablet", "tablet"),
    ("Phụ kiện", "phu-kien"),
    ("Đồng hồ thông minh", "dong-ho-thong-minh"),
    ("Tai nghe", "tai-nghe"),
    ("Máy ảnh", "may-anh"),
    ("PC & Linh kiện", "pc-linh-kien"),
    ("Gaming", "gaming"),
    ("Gia dụng thông minh", "gia-dung-thong-minh"),
]

BRANDS = {
    "dien-thoai": ["Samsung", "iPhone", "Xiaomi", "OPPO", "Vivo", "Realme", "Nothing", "Google Pixel"],
    "laptop": ["MacBook", "Dell", "HP", "Lenovo", "ASUS", "Acer", "MSI", "ThinkPad"],
    "tablet": ["iPad", "Samsung Tab", "Xiaomi Pad", "Lenovo Tab"],
    "phu-kien": ["Anker", "Baseus", "UGREEN", "Xiaomi", "ESR", "Spigen"],
    "dong-ho-thong-minh": ["Apple Watch", "Samsung Galaxy Watch", "Xiaomi Band", "Garmin", "Amazfit"],
    "tai-nghe": ["AirPods", "Sony", "JBL", "Samsung", "Xiaomi", "Sennheiser", "Bose"],
    "may-anh": ["Canon", "Nikon", "Sony", "Fujifilm", "GoPro"],
    "pc-linh-kien": ["Intel", "AMD", "NVIDIA", "Corsair", "Kingston", "Samsung SSD"],
    "gaming": ["PS5", "Xbox", "Nintendo", "Razer", "Logitech", "SteelSeries"],
    "gia-dung-thong-minh": ["Xiaomi", "Philips", "Dreame", "Roborock", "Ecovacs"],
}

ADJECTIVES = ["Pro", "Max", "Ultra", "Plus", "Lite", "SE", "2024", "2025", "Gen 2", "Gen 3", "Mini", "Air"]

COLORS = ["Đen", "Trắng", "Xanh dương", "Xanh lá", "Đỏ", "Vàng", "Tím", "Hồng", "Bạc", "Vàng đồng"]

SIZES = ["S", "M", "L", "XL", "64GB", "128GB", "256GB", "512GB", "1TB"]

POST_TITLES = [
    "Top 10 điện thoại đáng mua nhất 2025",
    "So sánh MacBook Air M3 vs MacBook Pro M3",
    "Hướng dẫn chọn tai nghe phù hợp",
    "Xu hướng công nghệ 2025",
    "Đánh giá chi tiết Samsung Galaxy S25 Ultra",
    "Cách bảo quản laptop đúng cách",
    "Tai nghe không dây tốt nhất dưới 2 triệu",
    "Máy ảnh du lịch tốt nhất cho người mới",
    "Xây dựng PC Gaming budget 15 triệu",
    "Robot hút bụi có đáng mua không?",
    "Apple Watch Series 10 có gì mới?",
    "Top 5 phụ kiện không thể thiếu cho điện thoại",
    "SSD vs HDD: Nên chọn loại nào?",
    "Cách tối ưu pin laptop hiệu quả",
    "iPhone 16 Pro Max đánh giá sau 3 tháng sử dụng",
]


def seed():
    """Generate all sample data."""
    print("🌱 Z-Core Seed Script")
    print("=" * 50)

    # Drop and recreate all tables
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = get_session()

    # ── Admin User ─────────────────────────────────────────
    admin = User(
        username="admin",
        email="admin@zcore.local",
        password_hash=hash_password("admin123"),
        display_name="Admin",
        role=UserRole.ADMIN,
    )
    db.add(admin)

    # Sample customer
    customer = User(
        username="customer",
        email="customer@example.com",
        password_hash=hash_password("customer123"),
        display_name="Nguyễn Văn A",
        role=UserRole.CUSTOMER,
    )
    db.add(customer)
    db.flush()
    print("✅ Users: admin/admin123, customer/customer123")

    # ── Categories ─────────────────────────────────────────
    cat_objects = {}
    for name, slug in CATEGORIES:
        cat = Category(name=name, slug=slug, description=f"Danh mục {name}")
        db.add(cat)
        db.flush()
        cat_objects[slug] = cat
    print(f"✅ Categories: {len(CATEGORIES)}")

    # ── Tags ───────────────────────────────────────────────
    tag_names = ["Mới", "Hot", "Sale", "Bán chạy", "Chính hãng", "Nhập khẩu", "Bảo hành 12T", "Free ship"]
    tag_objects = []
    for t in tag_names:
        tag = Tag(name=t, slug=t.lower().replace(" ", "-"))
        db.add(tag)
        tag_objects.append(tag)
    db.flush()
    print(f"✅ Tags: {len(tag_names)}")

    # ── 1000 Products ──────────────────────────────────────
    print("📦 Generating 1000 products...")
    product_count = 0

    for cat_slug, brands in BRANDS.items():
        cat = cat_objects[cat_slug]
        products_per_brand = 1000 // len(BRANDS) // len(brands) + 1

        for brand in brands:
            for i in range(products_per_brand):
                if product_count >= 1000:
                    break

                adj = random.choice(ADJECTIVES)
                name = f"{brand} {adj}"
                if random.random() > 0.5:
                    name += f" {random.choice(['', 'v2', 'v3', 'Gen {0}'.format(random.randint(2,5))])}"

                slug = f"{brand.lower().replace(' ', '-')}-{adj.lower().replace(' ', '-')}-{product_count + 1}"

                base_price = random.choice([
                    random.randint(500_000, 2_000_000),
                    random.randint(2_000_000, 10_000_000),
                    random.randint(10_000_000, 50_000_000),
                    random.randint(50_000_000, 150_000_000),
                ])

                sale_price = None
                if random.random() > 0.6:
                    sale_price = int(base_price * random.uniform(0.7, 0.95))

                stock_qty = random.randint(0, 500)
                stock_status = "instock" if stock_qty > 0 else "outofstock"

                gallery = []
                for _ in range(random.randint(0, 4)):
                    gallery.append(f"/static/uploads/products/sample-{random.randint(1,20)}.webp")

                product = Product(
                    name=name,
                    slug=slug,
                    sku=f"{brand.upper()[:3]}-{product_count + 1:04d}",
                    description=f"**{name}** chính hãng, bảo hành 12 tháng.\n\n"
                                f"## Thông số kỹ thuật\n"
                                f"- Thương hiệu: {brand}\n"
                                f"- Màu sắc: {random.choice(COLORS)}\n"
                                f"- Bảo hành: 12 tháng\n"
                                f"- Tình trạng: {'Mới 100%' if random.random() > 0.3 else 'Like new 99%'}\n\n"
                                f"## Mô tả\n"
                                f"Sản phẩm {name} với thiết kế hiện đại, hiệu năng mạnh mẽ. "
                                f"Phù hợp cho nhu cầu {random.choice(['học tập', 'làm việc', 'giải trí', 'gaming', 'sáng tạo nội dung'])}.",
                    short_description=f"{name} chính hãng, giá tốt nhất thị trường. Bảo hành 12 tháng.",
                    price=base_price,
                    sale_price=sale_price,
                    stock_quantity=stock_qty,
                    stock_status=stock_status,
                    manage_stock=True,
                    product_type=random.choice(["simple", "simple", "simple", "variable"]),
                    is_featured=random.random() > 0.9,
                    featured_image=f"/static/uploads/products/sample-{random.randint(1,20)}.webp",
                    gallery_images=json.dumps(gallery),
                    status=ProductStatus.PUBLISHED,
                    view_count=random.randint(0, 10000),
                    sales_count=random.randint(0, 500),
                    rating_avg=round(random.uniform(3.0, 5.0), 1),
                    rating_count=random.randint(0, 200),
                    published_at=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 365)),
                )
                product.categories.append(cat)

                # Random tags
                for tag in random.sample(tag_objects, random.randint(0, 3)):
                    product.tags.append(tag)

                db.add(product)
                db.flush()

                # Add variants for variable products
                if product.product_type == "variable":
                    attr = ProductAttribute(
                        product_id=product.id,
                        name="Màu sắc",
                        values=json.dumps(random.sample(COLORS, random.randint(2, 4))),
                        is_variation=True,
                    )
                    db.add(attr)
                    db.flush()

                    for ci, color in enumerate(random.sample(COLORS, random.randint(2, 4))):
                        variant = ProductVariant(
                            product_id=product.id,
                            sku=f"{product.sku}-{color[:3].upper()}-{ci}",
                            name=f"{color}",
                            price=base_price + random.randint(-500_000, 500_000),
                            stock_quantity=random.randint(0, 100),
                            stock_status="instock",
                        )
                        db.add(variant)

                product_count += 1

            if product_count >= 1000:
                break
        if product_count >= 1000:
            break

    db.flush()
    print(f"✅ Products: {product_count}")

    # ── Sample Posts ────────────────────────────────────────
    for i, title in enumerate(POST_TITLES):
        slug = title.lower()
        import re
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[-\s]+", "-", slug).strip("-")

        post = Post(
            title=title,
            slug=slug,
            content=f"# {title}\n\n"
                    f"Đây là bài viết đánh giá chi tiết về sản phẩm công nghệ. "
                    f"Nội dung bao gồm phân tích ưu nhược điểm, so sánh với đối thủ, "
                    f"và đưa ra lời khuyên mua hàng.\n\n"
                    f"## Ưu điểm\n- Thiết kế đẹp\n- Hiệu năng tốt\n- Giá hợp lý\n\n"
                    f"## Nhược điểm\n- Pin có thể tốt hơn\n- Một số tính năng chưa hoàn thiện\n\n"
                    f"## Kết luận\nSản phẩm đáng cân nhắc trong phân khúc giá.",
            excerpt=f"Bài viết đánh giá chi tiết {title.lower()}.",
            status=PostStatus.PUBLISHED,
            author_id=admin.id,
            featured_image=f"/static/uploads/posts/sample-{random.randint(1,10)}.webp",
            published_at=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 180)),
            view_count=random.randint(100, 50000),
        )
        db.add(post)

    db.flush()
    print(f"✅ Posts: {len(POST_TITLES)}")

    # ── Sample Pages ────────────────────────────────────────
    pages_data = [
        ("Giới thiệu", "gioi-thieu", "Chào mừng bạn đến với Z-Core Store. Chúng tôi cung cấp các sản phẩm công nghệ chính hãng với giá tốt nhất."),
        ("Liên hệ", "lien-he", "## Liên hệ với chúng tôi\n\n- **Địa chỉ:** 123 Nguyễn Huệ, Q.1, TP.HCM\n- **Điện thoại:** 0901234567\n- **Email:** contact@zcore.store"),
        ("Chính sách vận chuyển", "chinh-sach-van-chuyen", "## Chính sách vận chuyển\n\n- Miễn phí vận chuyển cho đơn hàng trên 500.000₫\n- Giao hàng trong 2-5 ngày làm việc\n- Hỗ trợ giao hàng nhanh trong 2h (nội thành)"),
        ("Chính sách đổi trả", "chinh-sach-doi-tra", "## Chính sách đổi trả\n\n- Đổi trả trong 7 ngày\n- Sản phẩm còn nguyên seal\n- Hoàn tiền trong 3-5 ngày làm việc"),
    ]
    for title, slug, content in pages_data:
        page = Page(
            title=title, slug=slug, content=content,
            status=PostStatus.PUBLISHED,
            published_at=datetime.now(timezone.utc),
        )
        db.add(page)
    db.flush()
    print(f"✅ Pages: {len(pages_data)}")

    # ── Sample Orders ──────────────────────────────────────
    import uuid
    for i in range(20):
        order_number = f"ZC-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        products = db.query(Product).filter(Product.status == ProductStatus.PUBLISHED).order_by(func.random()).limit(random.randint(1, 4)).all()

        items = []
        subtotal = 0
        for p in products:
            qty = random.randint(1, 3)
            price = p.sale_price or p.price
            items.append(OrderItem(
                product_id=p.id,
                product_name=p.name,
                product_sku=p.sku or "",
                price=price,
                quantity=qty,
                subtotal=price * qty,
            ))
            subtotal += price * qty

        order = Order(
            order_number=order_number,
            customer_id=customer.id,
            status=random.choice(list(OrderStatus)),
            customer_name="Nguyễn Văn A",
            customer_email="customer@example.com",
            customer_phone="0901234567",
            shipping_address=f"{random.randint(1,999)} Nguyễn Huệ",
            shipping_city="TP. Hồ Chí Minh",
            shipping_district="Quận 1",
            subtotal=subtotal,
            total=subtotal,
            payment_method=random.choice(["cod", "bank_transfer"]),
            items=items,
            created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 60)),
        )
        db.add(order)

    db.commit()
    print(f"✅ Orders: 20")

    # ── Site Options ────────────────────────────────────────
    options = {
        "site_title": "Z-Core Store",
        "site_description": "Cửa hàng công nghệ chính hãng",
        "site_logo": "/static/uploads/logo.png",
    }
    for k, v in options.items():
        db.add(Option(option_key=k, option_value=v))
    db.commit()
    db.close()

    print("\n" + "=" * 50)
    print("✅ Seed complete!")
    print(f"   Products: {product_count}")
    print(f"   Posts: {len(POST_TITLES)}")
    print(f"   Pages: {len(pages_data)}")
    print(f"   Orders: 20")
    print(f"   Admin: admin / admin123")


if __name__ == "__main__":
    # Need func.random for SQLite
    from sqlalchemy import func
    seed()
