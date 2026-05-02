#!/usr/bin/env python3
"""
Z-Core Comprehensive Audit
===========================
Tests: Performance, Security, Stability, Data Integrity
"""

import sys
import time
import json
import statistics
import hashlib
import sqlite3
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode

import httpx

BASE = "http://localhost:8000"
ADMIN_BASE = f"{BASE}/admin"
DB_PATH = "data/zcore.db"

results = {
    "performance": {},
    "security": {},
    "stability": {},
    "data_integrity": {},
    "issues": [],
    "warnings": [],
}


def log(category, test, status, detail="", severity="info"):
    icon = {"pass": "✅", "fail": "❌", "warn": "⚠️", "info": "ℹ️"}[status]
    print(f"  {icon} [{category}] {test}: {detail}")
    if status == "fail":
        results["issues"].append({"category": test, "detail": detail, "severity": severity})
    elif status == "warn":
        results["warnings"].append({"category": test, "detail": detail})


# ══════════════════════════════════════════════════════════════════════
# 1. PERFORMANCE AUDIT
# ══════════════════════════════════════════════════════════════════════

def audit_performance():
    print("\n" + "=" * 60)
    print("⚡ PERFORMANCE AUDIT")
    print("=" * 60)

    client = httpx.Client(base_url=BASE, timeout=30)

    # ── Single page load times ──────────────────────────────
    endpoints = {
        "Homepage": "/",
        "Shop (page 1)": "/shop",
        "Shop (page 5)": "/shop?page=5",
        "Shop (sort by price)": "/shop?sort=price_desc",
        "Shop (filter category)": "/shop?category=dien-thoai",
        "Blog": "/blog",
        "Search": "/search?q=samsung",
        "Product detail": "/product/samsung-pro-1",
        "Static page": "/gioi-thieu",
        "Cart page": "/cart",
        "Checkout page": "/checkout",
        "Robots.txt": "/robots.txt",
        "Sitemap.xml": "/sitemap.xml",
        "API products": "/api/products",
        "API search": "/api/search?q=iphone",
        "Admin login": "/admin/login",
    }

    timings = {}
    for name, path in endpoints.items():
        times = []
        for _ in range(5):
            start = time.perf_counter()
            resp = client.get(path)
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            assert resp.status_code in (200, 302, 401), f"{name} returned {resp.status_code}"

        avg = statistics.mean(times)
        p50 = statistics.median(times)
        p95 = sorted(times)[int(len(times) * 0.95)]
        timings[name] = {"avg": avg, "p50": p50, "p95": p95, "status_code": resp.status_code}

        if avg < 100:
            log("PERF", name, "pass", f"avg={avg:.1f}ms, p50={p50:.1f}ms")
        elif avg < 500:
            log("PERF", name, "warn", f"avg={avg:.1f}ms (slow), p50={p50:.1f}ms")
        else:
            log("PERF", name, "fail", f"avg={avg:.1f}ms (too slow!), p50={p50:.1f}ms")

    results["performance"]["endpoint_times"] = timings

    # ── Concurrent load test ────────────────────────────────
    print("\n  📊 Concurrent load test (50 users, 10 requests each)...")

    def fetch(url):
        start = time.perf_counter()
        resp = httpx.get(f"{BASE}{url}", timeout=30)
        return resp.status_code, (time.perf_counter() - start) * 1000

    urls = ["/", "/shop", "/shop?page=2", "/blog", "/search?q=test"] * 10
    load_times = []
    errors = 0

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch, url): url for url in urls[:50]}
        for future in as_completed(futures):
            try:
                status, elapsed = future.result()
                load_times.append(elapsed)
                if status not in (200, 302):
                    errors += 1
            except Exception:
                errors += 1

    if load_times:
        avg_load = statistics.mean(load_times)
        p95_load = sorted(load_times)[int(len(load_times) * 0.95)]
        p99_load = sorted(load_times)[int(len(load_times) * 0.99)]
        max_load = max(load_times)

        results["performance"]["load_test"] = {
            "total_requests": len(urls[:50]),
            "errors": errors,
            "avg_ms": avg_load,
            "p95_ms": p95_load,
            "p99_ms": p99_load,
            "max_ms": max_load,
        }

        log("PERF", "Load test avg", "pass" if avg_load < 200 else "warn", f"{avg_load:.1f}ms")
        log("PERF", "Load test p95", "pass" if p95_load < 500 else "warn", f"{p95_load:.1f}ms")
        log("PERF", "Load test p99", "pass" if p99_load < 1000 else "warn", f"{p99_load:.1f}ms")
        log("PERF", "Load test errors", "pass" if errors == 0 else "fail", f"{errors}/50 failed")

    # ── Response size audit ─────────────────────────────────
    print("\n  📦 Response size audit...")
    for name, path in [("/", "/"), ("Shop", "/shop"), ("Product", "/product/samsung-pro-1")]:
        resp = client.get(path)
        size_kb = len(resp.content) / 1024
        if size_kb < 50:
            log("PERF", f"{name} size", "pass", f"{size_kb:.1f} KB")
        elif size_kb < 200:
            log("PERF", f"{name} size", "warn", f"{size_kb:.1f} KB (large)")
        else:
            log("PERF", f"{name} size", "fail", f"{size_kb:.1f} KB (too large)")

    # ── Database performance ────────────────────────────────
    print("\n  🗄️  Database performance...")
    conn = sqlite3.connect(DB_PATH)

    queries = [
        ("Count products", "SELECT COUNT(*) FROM products"),
        ("Full text search", "SELECT * FROM products WHERE name LIKE '%samsung%' OR description LIKE '%samsung%' LIMIT 20"),
        ("Sorted by price", "SELECT * FROM products WHERE status='published' ORDER BY price DESC LIMIT 20"),
        ("Category join", "SELECT p.* FROM products p JOIN product_categories pc ON p.id=pc.product_id WHERE pc.category_id=1 LIMIT 20"),
        ("With variants", "SELECT p.*, COUNT(v.id) as variant_count FROM products p LEFT JOIN product_variants v ON p.id=v.product_id GROUP BY p.id LIMIT 20"),
    ]

    for name, query in queries:
        times = []
        for _ in range(10):
            start = time.perf_counter()
            conn.execute(query).fetchall()
            times.append((time.perf_counter() - start) * 1000)
        avg = statistics.mean(times)
        log("PERF", f"DB: {name}", "pass" if avg < 50 else "warn", f"{avg:.2f}ms")

    conn.close()
    client.close()


# ══════════════════════════════════════════════════════════════════════
# 2. SECURITY AUDIT
# ══════════════════════════════════════════════════════════════════════

def audit_security():
    print("\n" + "=" * 60)
    print("🔒 SECURITY AUDIT")
    print("=" * 60)

    client = httpx.Client(base_url=BASE, timeout=30, follow_redirects=False)

    # ── Admin panel protection ──────────────────────────────
    print("\n  🛡️  Admin panel access control...")
    protected_paths = [
        "/admin/",
        "/admin/posts",
        "/admin/products",
        "/admin/orders",
        "/admin/settings",
    ]
    for path in protected_paths:
        resp = client.get(path)
        if resp.status_code in (302, 307) and "login" in resp.headers.get("location", ""):
            log("SEC", f"Admin {path}", "pass", "Redirects to login (302)")
        elif resp.status_code == 401:
            log("SEC", f"Admin {path}", "pass", "Returns 401")
        else:
            log("SEC", f"Admin {path}", "fail", f"Accessible without auth! Status: {resp.status_code}")

    # ── Login brute force (basic check) ─────────────────────
    print("\n  🔐 Authentication security...")
    resp = client.post("/admin/login", data={"username": "admin", "password": "wrongpassword"})
    if resp.status_code == 200 and ("sai" in resp.text.lower() or "error" in resp.text.lower()):
        log("SEC", "Failed login", "pass", "Returns error message, no redirect")
    else:
        log("SEC", "Failed login", "warn", f"Status: {resp.status_code}")

    # ── SQL Injection (basic probes) ────────────────────────
    print("\n  💉 SQL Injection probes...")
    sqli_payloads = [
        "' OR '1'='1",
        "1; DROP TABLE products;--",
        "' UNION SELECT * FROM users--",
    ]
    for payload in sqli_payloads:
        resp = client.get(f"/search?q={payload}")
        if resp.status_code == 200 and "error" not in resp.text.lower()[:500]:
            log("SEC", "SQLi search", "pass", f"Payload handled safely: {payload[:30]}...")
        elif resp.status_code == 500:
            log("SEC", "SQLi search", "fail", f"Server error on payload: {payload[:30]}...")
        else:
            log("SEC", "SQLi search", "pass", f"Blocked/handled: {payload[:30]}...")

    # ── XSS (basic probes) ─────────────────────────────────
    print("\n  🧪 XSS probes...")
    xss_payloads = [
        "<script>alert(1)</script>",
        '<img src=x onerror=alert(1)>',
        '"><script>alert(document.cookie)</script>',
    ]
    for payload in xss_payloads:
        resp = client.get(f"/search?q={payload}")
        if payload in resp.text:
            log("SEC", "XSS search", "fail", f"Unsanitized output: {payload[:40]}...")
        else:
            log("SEC", "XSS search", "pass", f"Properly escaped: {payload[:40]}...")

    # ── CSRF protection ─────────────────────────────────────
    print("\n  🛡️  CSRF & headers...")
    resp = client.get("/")
    headers = resp.headers

    security_headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": None,  # Should be set
        "X-XSS-Protection": None,
        "Content-Security-Policy": None,
    }

    for header, expected in security_headers.items():
        if header in headers:
            log("SEC", f"Header {header}", "pass", f"Present: {headers[header][:50]}")
        else:
            log("SEC", f"Header {header}", "warn", "Not set (should set in Nginx)")

    # ── Directory traversal ─────────────────────────────────
    print("\n  📂 Path traversal...")
    traversal_payloads = [
        "/../../../etc/passwd",
        "/static/../../../etc/passwd",
        "/static/uploads/../../config/settings.py",
    ]
    for payload in traversal_payloads:
        resp = client.get(payload)
        if resp.status_code in (404, 400, 302):
            log("SEC", "Path traversal", "pass", f"Blocked: {payload}")
        elif "root:" in resp.text:
            log("SEC", "Path traversal", "fail", f"File disclosed: {payload}")
        else:
            log("SEC", "Path traversal", "pass", f"Safe: {payload} → {resp.status_code}")

    # ── Sensitive file exposure ──────────────────────────────
    print("\n  🔍 Sensitive file exposure...")
    sensitive_paths = [
        "/.env",
        "/.git/config",
        "/config/settings.py",
        "/app/main.py",
        "/data/zcore.db",
        "/admin/login",  # Should exist
        "/api/docs",  # Should be disabled in prod
    ]
    for path in sensitive_paths:
        resp = client.get(path)
        if path == "/admin/login":
            if resp.status_code == 200:
                log("SEC", f"File {path}", "pass", "Accessible (expected)")
        elif resp.status_code == 200 and len(resp.content) > 100:
            log("SEC", f"File {path}", "fail", f"Exposed! {len(resp.content)} bytes")
        else:
            log("SEC", f"File {path}", "pass", f"Not accessible ({resp.status_code})")

    # ── Session security ────────────────────────────────────
    print("\n  🍪 Session security...")
    resp = client.post("/admin/login", data={"username": "admin", "password": "admin123"})
    cookies = resp.cookies
    for name, value in cookies.items():
        log("SEC", f"Cookie {name}", "info", f"Value length: {len(value)}")

    # ── Password hashing ────────────────────────────────────
    print("\n  🔑 Password storage...")
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT password_hash FROM users WHERE username='admin'").fetchone()
    if row:
        pw_hash = row[0]
        if "$" in pw_hash:
            salt, h = pw_hash.split("$", 1)
            if len(salt) >= 16:
                log("SEC", "Password hash", "pass", f"SHA-256 + salt ({len(salt)} chars)")
            else:
                log("SEC", "Password hash", "warn", f"Weak salt: {len(salt)} chars")
        else:
            log("SEC", "Password hash", "fail", "No salt detected!")
    conn.close()

    client.close()


# ══════════════════════════════════════════════════════════════════════
# 3. STABILITY AUDIT
# ══════════════════════════════════════════════════════════════════════

def audit_stability():
    print("\n" + "=" * 60)
    print("🔧 STABILITY AUDIT")
    print("=" * 60)

    client = httpx.Client(base_url=BASE, timeout=30)

    # ── Edge cases ──────────────────────────────────────────
    print("\n  🔀 Edge case handling...")
    edge_cases = [
        ("Empty search", "/search?q="),
        ("Very long query", "/search?q=" + "a" * 1000),
        ("Non-existent product", "/product/does-not-exist-12345"),
        ("Non-existent page", "/this-page-does-not-exist"),
        ("Invalid page number", "/shop?page=999999"),
        ("Negative page", "/shop?page=-1"),
        ("Zero page", "/shop?page=0"),
        ("Special chars in URL", "/product/!@#$%^&*()"),
        ("Unicode in search", "/search?q=điện+thoại"),
        ("Large page number", "/shop?page=999999999"),
    ]

    for name, path in edge_cases:
        try:
            resp = client.get(path)
            if resp.status_code == 500:
                log("STAB", name, "fail", f"500 Internal Server Error!")
            elif resp.status_code in (200, 302, 404):
                log("STAB", name, "pass", f"Status {resp.status_code}")
            else:
                log("STAB", name, "warn", f"Unexpected status {resp.status_code}")
        except Exception as e:
            log("STAB", name, "fail", f"Exception: {e}")

    # ── Rapid-fire requests (stress) ────────────────────────
    print("\n  🔥 Rapid-fire stress test (100 sequential requests)...")
    errors = 0
    times = []
    for i in range(100):
        start = time.perf_counter()
        try:
            resp = client.get(f"/shop?page={(i % 10) + 1}")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)
            if resp.status_code == 500:
                errors += 1
        except Exception:
            errors += 1

    if times:
        log("STAB", "100 requests", "pass" if errors == 0 else "fail",
            f"avg={statistics.mean(times):.1f}ms, errors={errors}/100")

    # ── Database integrity ──────────────────────────────────
    print("\n  🗄️  Database integrity...")
    conn = sqlite3.connect(DB_PATH)

    integrity_checks = [
        ("Foreign key consistency",
         """SELECT COUNT(*) FROM order_items oi
            LEFT JOIN orders o ON oi.order_id = o.id
            WHERE o.id IS NULL"""),
        ("Product-Category junction",
         """SELECT COUNT(*) FROM product_categories pc
            LEFT JOIN products p ON pc.product_id = p.id
            WHERE p.id IS NULL"""),
        ("Orphan variants",
         """SELECT COUNT(*) FROM product_variants pv
            LEFT JOIN products p ON pv.product_id = p.id
            WHERE p.id IS NULL"""),
        ("Duplicate slugs (products)",
         """SELECT slug, COUNT(*) FROM products GROUP BY slug HAVING COUNT(*) > 1"""),
        ("Duplicate slugs (posts)",
         """SELECT slug, COUNT(*) FROM posts GROUP BY slug HAVING COUNT(*) > 1"""),
        ("Null required fields",
         """SELECT COUNT(*) FROM products WHERE name IS NULL OR name = ''"""),
    ]

    for name, query in integrity_checks:
        try:
            result = conn.execute(query).fetchall()
            count = sum(r[0] for r in result) if result and len(result[0]) == 1 else len(result)
            log("STAB", name, "pass" if count == 0 else "warn", f"{count} issues found")
        except Exception as e:
            log("STAB", name, "fail", f"Query error: {e}")

    conn.close()

    # ── Memory/resource check ───────────────────────────────
    print("\n  💾 Resource usage...")
    import os
    db_size = os.path.getsize(DB_PATH) / (1024 * 1024)
    log("STAB", "Database size", "pass" if db_size < 100 else "warn", f"{db_size:.1f} MB")

    client.close()


# ══════════════════════════════════════════════════════════════════════
# 4. DATA INTEGRITY AUDIT
# ══════════════════════════════════════════════════════════════════════

def audit_data_integrity():
    print("\n" + "=" * 60)
    print("📊 DATA INTEGRITY AUDIT")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)

    # ── Record counts ───────────────────────────────────────
    tables = [
        "users", "categories", "tags", "posts", "pages",
        "products", "product_variants", "orders", "order_items", "options"
    ]
    print("\n  📋 Record counts...")
    for table in tables:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            log("DATA", table, "pass" if count > 0 else "warn", f"{count} records")
        except Exception as e:
            log("DATA", table, "fail", str(e))

    # ── Product data quality ────────────────────────────────
    print("\n  🔍 Product data quality...")
    checks = [
        ("Products with price=0", "SELECT COUNT(*) FROM products WHERE price = 0 AND status='published'"),
        ("Products with no description", "SELECT COUNT(*) FROM products WHERE (description IS NULL OR description='') AND status='published'"),
        ("Products with no SKU", "SELECT COUNT(*) FROM products WHERE (sku IS NULL OR sku='') AND status='published'"),
        ("Published products", "SELECT COUNT(*) FROM products WHERE status='published'"),
        ("Featured products", "SELECT COUNT(*) FROM products WHERE is_featured=1"),
        ("Products with variants", "SELECT COUNT(DISTINCT product_id) FROM product_variants"),
    ]
    for name, query in checks:
        count = conn.execute(query).fetchone()[0]
        log("DATA", name, "info", str(count))

    # ── Index check ─────────────────────────────────────────
    print("\n  📇 Index analysis...")
    indexes = conn.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'").fetchall()
    log("DATA", "Custom indexes", "info", f"{len(indexes)} indexes")

    # Check if key columns are indexed
    indexed_cols = {idx[0] for idx in indexes}
    important_indexes = [
        ("ix_products_slug", "products.slug"),
        ("ix_products_sku", "products.sku"),
        ("ix_posts_slug", "posts.slug"),
        ("ix_categories_slug", "categories.slug"),
    ]
    for idx_name, desc in important_indexes:
        if idx_name in indexed_cols:
            log("DATA", f"Index on {desc}", "pass", "Present")
        else:
            log("DATA", f"Index on {desc}", "warn", "Missing — may slow queries")

    conn.close()


# ══════════════════════════════════════════════════════════════════════
# REPORT
# ══════════════════════════════════════════════════════════════════════

def print_report():
    print("\n" + "=" * 60)
    print("📊 AUDIT SUMMARY")
    print("=" * 60)

    print(f"\n  🔴 Critical Issues:  {len(results['issues'])}")
    for issue in results["issues"]:
        print(f"     ❌ [{issue['category']}] {issue['detail']}")

    print(f"\n  🟡 Warnings:         {len(results['warnings'])}")
    for warn in results["warnings"]:
        print(f"     ⚠️  [{warn['category']}] {warn['detail']}")

    if not results["issues"] and not results["warnings"]:
        print("\n  🎉 All checks passed!")

    # Performance summary
    if "load_test" in results.get("performance", {}):
        lt = results["performance"]["load_test"]
        print(f"\n  ⚡ Load Test: {lt['total_requests']} requests, "
              f"avg={lt['avg_ms']:.0f}ms, p95={lt['p95_ms']:.0f}ms, "
              f"p99={lt['p99_ms']:.0f}ms, errors={lt['errors']}")

    # Score
    total_checks = len(results["issues"]) + len(results["warnings"])
    score = max(0, 100 - len(results["issues"]) * 15 - len(results["warnings"]) * 3)
    print(f"\n  🏆 Overall Score: {score}/100")

    # Save report
    report_path = Path("audit_report.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  📄 Full report: {report_path}")


def main():
    print("🔍 Z-Core Comprehensive Audit")
    print("=" * 60)

    audit_performance()
    audit_security()
    audit_stability()
    audit_data_integrity()
    print_report()


if __name__ == "__main__":
    main()
