from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, Column, Integer, String, Text, DateTime
from pydantic import BaseModel
from typing import Optional, List
from database import get_db, Base, engine, Product, PurchaseOrder, User
from auth import get_current_user, require_editor
from datetime import datetime, timezone, timedelta
import httpx
import os
import json
import hashlib

router = APIRouter(prefix="/api/wecom", tags=["企业微信集成"])


# Notification log model
class NotificationLog(Base):
    __tablename__ = "notification_logs"
    id = Column(Integer, primary_key=True, index=True)
    notification_type = Column(String(50), nullable=False)
    content = Column(Text, default="")
    status = Column(String(20), default="sent")
    sent_to = Column(String(200), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(bind=engine)


class WecomMessage(BaseModel):
    msg_type: str = "text"
    content: str
    user_ids: Optional[List[str]] = None


class WecomConfig(BaseModel):
    webhook_url: str = ""
    bot_token: str = ""
    enabled: bool = False


@router.get("/config")
def get_config(user: User = Depends(get_current_user)):
    return {
        "webhook_url": os.getenv("WECOM_WEBHOOK_URL", ""),
        "bot_token": os.getenv("WECOM_BOT_TOKEN", ""),
        "enabled": bool(os.getenv("WECOM_WEBHOOK_URL", "")),
    }


@router.post("/send")
async def send_message(
    msg: WecomMessage,
    user: User = Depends(require_editor),
):
    """通过企业微信群机器人发送消息"""
    webhook_url = os.getenv("WECOM_WEBHOOK_URL", "")
    if not webhook_url:
        raise HTTPException(status_code=400, detail="未配置企业微信Webhook URL")

    payload = {"msgtype": "text", "text": {"content": msg.content}}
    if msg.user_ids:
        payload["text"]["mentioned_list"] = msg.user_ids

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(webhook_url, json=payload)

    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"发送失败: {resp.text}")

    return {"message": "发送成功", "errcode": 0}


@router.post("/notify/low-stock")
async def notify_low_stock(
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    """通知低库存商品"""
    webhook_url = os.getenv("WECOM_WEBHOOK_URL", "")
    if not webhook_url:
        raise HTTPException(status_code=400, detail="未配置企业微信Webhook URL")

    low_stock = (
        db.query(Product)
        .filter(Product.stock_quantity < 10, Product.status != "停售")
        .order_by(Product.stock_quantity.asc())
        .limit(10)
        .all()
    )

    if not low_stock:
        return {"message": "没有低库存商品"}

    content = "⚠️ 低库存预警\n"
    for p in low_stock:
        content += f"\n- {p.sku} {p.product_name}\n  库存: {p.stock_quantity} | 1688价: ¥{p.price_1688}"
    content += "\n\n请及时安排补货 → 查看详情"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            webhook_url,
            json={"msgtype": "text", "text": {"content": content}},
        )

    return {"message": "通知已发送", "low_stock_count": len(low_stock)}


@router.post("/notify/order-status")
async def notify_order_status(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    """通知采购单状态变更"""
    webhook_url = os.getenv("WECOM_WEBHOOK_URL", "")
    if not webhook_url:
        raise HTTPException(status_code=400, detail="未配置企业微信Webhook URL")

    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="采购单不存在")

    content = (
        f"📋 采购单更新\n"
        f"单号: {order.order_number}\n"
        f"供应商: {order.supplier}\n"
        f"金额: ¥{order.total_amount:.2f}\n"
        f"状态: {order.status}\n"
        f"创建人: {order.creator.display_name if order.creator else ''}"
    )

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            webhook_url,
            json={"msgtype": "text", "text": {"content": content}},
        )

    return {"message": "通知已发送"}


def log_notification(db: Session, notif_type: str, content: str, status: str = "sent", sent_to: str = ""):
    """记录通知日志"""
    log = NotificationLog(
        notification_type=notif_type,
        content=content[:500],
        status=status,
        sent_to=sent_to,
    )
    db.add(log)
    db.commit()


@router.post("/notify/daily-summary")
async def notify_daily_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    """发送每日数据汇总通知"""
    webhook_url = os.getenv("WECOM_WEBHOOK_URL", "")
    if not webhook_url:
        raise HTTPException(status_code=400, detail="未配置企业微信Webhook URL")

    # 统计数据
    total = db.query(Product).count()
    low_stock = db.query(Product).filter(
        Product.stock_quantity < 10, Product.stock_quantity > 0
    ).count()
    out_of_stock = db.query(Product).filter(Product.stock_quantity == 0).count()
    pending = db.query(Product).filter(Product.status == "待采购").count()

    # 今日新增
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_new = db.query(Product).filter(Product.created_at >= today_start).count()

    # 分类统计
    top_categories = (
        db.query(Product.category, func.count(Product.id))
        .filter(Product.category != "", Product.category.isnot(None))
        .group_by(Product.category)
        .order_by(func.count(Product.id).desc())
        .limit(5)
        .all()
    )

    content = "📊 每日数据汇总\n"
    content += f"━━━━━━━━━━━━━━\n"
    content += f"📦 总产品数: {total}\n"
    content += f"➕ 今日新增: {today_new}\n"
    content += f"🔴 缺货: {out_of_stock}\n"
    content += f"🟡 低库存(<10): {low_stock}\n"
    content += f"📋 待采购: {pending}\n"
    content += f"━━━━━━━━━━━━━━\n"
    content += f"📂 主要分类:\n"
    for cat, cnt in top_categories:
        content += f"  · {cat}: {cnt}个\n"
    content += f"\n🔗 查看详情: https://procurement-system-nq85.onrender.com"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            webhook_url,
            json={"msgtype": "text", "text": {"content": content}},
        )

    if resp.status_code == 200:
        log_notification(db, "daily_summary", content)
        return {"message": "每日汇总已发送", "data": {"total": total, "low_stock": low_stock, "out_of_stock": out_of_stock}}
    raise HTTPException(status_code=500, detail=f"发送失败: {resp.text}")


@router.post("/notify/auto-check")
async def auto_check_and_notify(
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    """自动检查库存和待办事项并发送通知"""
    webhook_url = os.getenv("WECOM_WEBHOOK_URL", "")
    if not webhook_url:
        raise HTTPException(status_code=400, detail="未配置企业微信Webhook URL")

    # 检查低库存
    low_stock_products = (
        db.query(Product)
        .filter(Product.stock_quantity < 10, Product.status != "停售")
        .order_by(Product.stock_quantity.asc())
        .limit(10)
        .all()
    )

    # 检查待采购超过7天
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    overdue_pending = (
        db.query(Product)
        .filter(
            Product.status == "待采购",
            Product.updated_at < seven_days_ago,
        )
        .limit(10)
        .all()
    )

    content_parts = []
    if low_stock_products:
        part = "⚠️ 低库存预警\n"
        for p in low_stock_products:
            part += f"\n🔴 {p.sku} {p.product_name}\n  库存: {p.stock_quantity} | ¥{p.purchase_price}"
        content_parts.append(part)

    if overdue_pending:
        part = "⏰ 待采购超期提醒（>7天）\n"
        for p in overdue_pending:
            part += f"\n📋 {p.sku} {p.product_name}\n  供应商: {p.supplier}"
        content_parts.append(part)

    if not content_parts:
        return {"message": "当前无异常，无需通知", "status": "ok"}

    full_content = "\n\n".join(content_parts)
    full_content += "\n\n🔗 前往系统查看详情"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            webhook_url,
            json={"msgtype": "text", "text": {"content": full_content}},
        )

    if resp.status_code == 200:
        log_notification(db, "auto_check", full_content)
        return {
            "message": "检查完成并已发送通知",
            "low_stock_count": len(low_stock_products),
            "overdue_count": len(overdue_pending),
        }
    raise HTTPException(status_code=500, detail=f"发送失败: {resp.text}")


@router.get("/notification-logs")
def get_notification_logs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取通知历史记录"""
    logs = (
        db.query(NotificationLog)
        .order_by(NotificationLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": log.id,
            "type": log.notification_type,
            "content": log.content[:200],
            "status": log.status,
            "created_at": log.created_at.isoformat() if log.created_at else "",
        }
        for log in logs
    ]


@router.post("/webhook")
async def handle_webhook(data: dict):
    """接收企业微信回调"""
    # 验证消息签名
    token = os.getenv("WECOM_BOT_TOKEN", "")
    if token:
        msg_signature = data.get("msg_signature", "")
        timestamp = data.get("timestamp", "")
        nonce = data.get("nonce", "")
        echo_str = data.get("echostr", "")

        if echo_str:
            # 验证URL
            sort_list = sorted([token, timestamp, nonce, echo_str])
            sha1 = hashlib.sha1("".join(sort_list).encode()).hexdigest()
            if sha1 == msg_signature:
                return {"echostr": echo_str}
            raise HTTPException(status_code=403, detail="签名验证失败")

    return {"errcode": 0, "errmsg": "ok"}