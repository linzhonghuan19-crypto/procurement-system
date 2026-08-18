from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from database import get_db, Product, PurchaseOrder, User
from auth import get_current_user, require_editor
import httpx
import os
import json
import hashlib

router = APIRouter(prefix="/api/wecom", tags=["企业微信集成"])


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