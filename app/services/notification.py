"""
Z-Core Notification Service
============================
Telegram Bot + Email SMTP notifications for new orders.
"""

import asyncio
import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


async def send_telegram(message: str) -> bool:
    """Send message via Telegram Bot API."""
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured, skipping notification")
        return False

    try:
        import httpx
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
            })
            return resp.status_code == 200
    except Exception as e:
        logger.error(f"Telegram notification failed: {e}")
        return False


async def send_email(to: str, subject: str, body: str) -> bool:
    """Send email via SMTP."""
    if not settings.SMTP_HOST:
        logger.warning("SMTP not configured, skipping email notification")
        return False

    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart()
        msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html", "utf-8"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_TLS:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASS)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"Email notification failed: {e}")
        return False


def format_order_telegram(order) -> str:
    """Format order details for Telegram notification."""
    items_text = ""
    for item in order.items:
        items_text += f"  • {item.product_name}"
        if item.variant_name:
            items_text += f" ({item.variant_name})"
        items_text += f" × {item.quantity} = {item.subtotal:,.0f}₫\n"

    return f"""🆕 <b>Đơn hàng mới #{order.order_number}</b>

👤 {order.customer_name}
📞 {order.customer_email}
📍 {order.shipping_address}, {order.shipping_district}, {order.shipping_city}

🛒 <b>Sản phẩm:</b>
{items_text}
💰 <b>Tổng cộng: {order.total:,.0f}₫</b>
📦 Thanh toán: {order.payment_method}
📝 {order.customer_note or 'Không có ghi chú'}
"""


def format_order_email(order) -> str:
    """Format order details for email notification."""
    items_html = ""
    for item in order.items:
        variant = f" ({item.variant_name})" if item.variant_name else ""
        items_html += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #eee">{item.product_name}{variant}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;text-align:center">{item.quantity}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;text-align:right">{item.subtotal:,.0f}₫</td>
        </tr>"""

    return f"""
    <div style="font-family:sans-serif;max-width:600px;margin:0 auto">
        <h2 style="color:#333">🛒 Đơn hàng mới #{order.order_number}</h2>
        <p><strong>Khách hàng:</strong> {order.customer_name}</p>
        <p><strong>Email:</strong> {order.customer_email}</p>
        <p><strong>Điện thoại:</strong> {order.customer_phone}</p>
        <p><strong>Địa chỉ:</strong> {order.shipping_address}, {order.shipping_district}, {order.shipping_city}</p>

        <table style="width:100%;border-collapse:collapse;margin:20px 0">
            <thead>
                <tr style="background:#f8f9fa">
                    <th style="padding:8px;text-align:left;border-bottom:2px solid #ddd">Sản phẩm</th>
                    <th style="padding:8px;text-align:center;border-bottom:2px solid #ddd">SL</th>
                    <th style="padding:8px;text-align:right;border-bottom:2px solid #ddd">Thành tiền</th>
                </tr>
            </thead>
            <tbody>{items_html}</tbody>
            <tfoot>
                <tr>
                    <td colspan="2" style="padding:8px;text-align:right"><strong>Tổng cộng:</strong></td>
                    <td style="padding:8px;text-align:right;color:#e63946;font-size:18px"><strong>{order.total:,.0f}₫</strong></td>
                </tr>
            </tfoot>
        </table>

        <p><strong>Ghi chú:</strong> {order.customer_note or 'Không có'}</p>
        <p><strong>Thanh toán:</strong> {order.payment_method}</p>
    </div>
    """


async def notify_new_order(order, db=None):
    """Send notifications for a new order (Telegram + Email)."""
    telegram_msg = format_order_telegram(order)
    email_body = format_order_email(order)

    # Send Telegram
    tg_ok = await send_telegram(telegram_msg)
    if tg_ok and db:
        order.telegram_notified = True

    # Send email to admin
    if settings.SMTP_FROM:
        email_ok = await send_email(settings.SMTP_FROM, f"Đơn hàng mới #{order.order_number}", email_body)
        if email_ok and db:
            order.email_notified = True

    # Send confirmation email to customer
    if order.customer_email:
        await send_email(
            order.customer_email,
            f"Xác nhận đơn hàng #{order.order_number}",
            f"<p>Cảm ơn bạn đã đặt hàng! Đơn hàng #{order.order_number} đã được nhận.</p>{email_body}"
        )

    if db:
        db.commit()
