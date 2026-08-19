from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from database import get_db, Product, User, PurchaseOrder, OrderItem
from auth import get_current_user, require_editor
from datetime import datetime, timedelta
import os
import json

router = APIRouter(prefix="/api/ai", tags=["AI智能"])


class AIAnalysisRequest(BaseModel):
    query: str
    product_ids: Optional[List[int]] = None


class AIFillRequest(BaseModel):
    purchase_link: str
    product_name: Optional[str] = None


class AIClassifyRequest(BaseModel):
    product_ids: List[int]
    category: Optional[str] = None


class AISummaryRequest(BaseModel):
    group_by: str = "category"  # category, status, supplier, attribute
    date_range: Optional[int] = None  # days


def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY", "")
    api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key, base_url=api_base)
    except ImportError:
        return None


def get_ai_response(messages, model="gpt-4o-mini"):
    client = get_openai_client()
    if not client:
        return None
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI请求失败: {str(e)}"


@router.post("/analyze")
def ai_analyze(
    req: AIAnalysisRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """AI分析采购数据"""
    products_query = db.query(Product)
    if req.product_ids:
        products_query = products_query.filter(Product.id.in_(req.product_ids))
    products = products_query.order_by(Product.updated_at.desc()).limit(50).all()

    if not products:
        return {"reply": "没有找到可分析的产品数据"}

    product_summary = []
    for p in products:
        product_summary.append(
            f"SKU:{p.sku} | 名称:{p.product_name} | 类目:{p.category} | "
            f"1688价:{p.price_1688} | 亚马逊价:{p.price_amazon} | 售价:{p.price_selling} | "
            f"库存:{p.stock_quantity} | 供应商:{p.supplier} | 状态:{p.status}"
        )

    system_prompt = """你是海外仓采购智能助手，擅长分析采购数据并提供决策建议。
请根据用户的问题和产品数据，给出专业的分析和建议。包括但不限于：
1. 价格分析和比价建议
2. 库存预警和补货建议
3. 供应商评估
4. 利润分析
5. 采购优先级排序

请用中文回答，简洁专业。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"用户问题: {req.query}\n\n产品数据:\n" + "\n".join(product_summary)},
    ]

    reply = get_ai_response(messages)
    if reply is None:
        # 没有配置API Key，本地分析
        reply = local_analysis(req.query, products)

    return {"reply": reply, "product_count": len(products)}


@router.post("/fill-product")
def ai_fill_product(
    req: AIFillRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    """根据采购链接AI自动提取商品信息"""
    if not req.purchase_link:
        raise HTTPException(status_code=400, detail="请提供采购链接")

    # 先尝试用AI提取
    system_prompt = """你是一个电商采购助手。根据用户提供的商品链接和商品名，提取商品信息并返回JSON。
请返回以下JSON格式（不要加markdown标记）：
{
  "product_name": "商品名称",
  "category": "商品类目（如：电子产品/家居/服装等）",
  "price_1688": 0.0,
  "supplier": "供应商名称",
  "remarks": "从链接中提取的备注信息"
}
如果无法从链接中提取到信息，请合理推测，价格填0。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"采购链接: {req.purchase_link}\n商品名称(可选): {req.product_name or '未知'}"},
    ]

    reply = get_ai_response(messages)
    result = {"product_name": req.product_name or "", "category": "", "price_1688": 0, "supplier": "", "remarks": ""}

    if reply:
        try:
            cleaned = reply.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(cleaned)
            result.update(parsed)
        except (json.JSONDecodeError, AttributeError):
            pass

    return {"success": True, "data": result}


@router.post("/suggest-order")
def ai_suggest_order(
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    """AI建议生成采购单"""
    pending = (
        db.query(Product)
        .filter(Product.status.in_(["待采购"]), Product.stock_quantity < 10)
        .order_by(Product.stock_quantity.asc())
        .limit(30)
        .all()
    )

    if not pending:
        return {"message": "当前没有需要采购的商品", "items": []}

    suggestions = []
    for p in pending:
        suggestions.append(
            f"SKU:{p.sku} | {p.product_name} | 库存:{p.stock_quantity} | "
            f"1688价:{p.price_1688} | 供应商:{p.supplier}"
        )

    system_prompt = """你是采购助手。根据以下库存不足的商品列表，建议合理的采购数量和供应商。
请返回JSON格式（不要加markdown标记）：
{
  "supplier": "建议的供应商",
  "items": [
    {"sku": "SKU001", "suggested_quantity": 100, "reason": "建议理由"},
    {"sku": "SKU002", "suggested_quantity": 50, "reason": "建议理由"}
  ],
  "notes": "采购备注"
}
数量建议要合理，考虑MOQ和库存周转。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "需要采购的商品:\n" + "\n".join(suggestions)},
    ]

    reply = get_ai_response(messages)
    items = []
    if reply:
        try:
            cleaned = reply.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(cleaned)
            items = parsed.get("items", [])
        except (json.JSONDecodeError, AttributeError):
            pass

    return {
        "message": "AI建议已生成",
        "items": items,
        "pending_count": len(pending),
    }


def local_analysis(query: str, products: list) -> str:
    """无AI API时的本地分析"""
    total = len(products)
    low_stock = [p for p in products if p.stock_quantity < 10]
    out_of_stock = [p for p in products if p.stock_quantity == 0]
    pending = [p for p in products if p.status == "待采购"]

    analysis = f"📊 共 {total} 个产品\n"
    analysis += f"🔴 缺货: {len(out_of_stock)} 个\n"
    analysis += f"🟡 低库存(<10): {len(low_stock)} 个\n"
    analysis += f"📋 待采购: {len(pending)} 个\n\n"

    if out_of_stock:
        analysis += "⚠️ 紧急缺货:\n"
        for p in out_of_stock[:5]:
            analysis += f"  - {p.sku} {p.product_name}\n"

    if "分析" in query or "建议" in query:
        if pending:
            analysis += "\n💡 建议优先采购以下商品:\n"
            for p in pending[:5]:
                analysis += f"  - {p.sku} {p.product_name} (库存:{p.stock_quantity})\n"

    if not analysis.strip():
        analysis = f"本地数据统计完成。共{total}个产品，可使用AI获取更深入分析（需配置OpenAI API Key）。"

    return analysis


@router.post("/classify")
def ai_classify(
    req: AIClassifyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """AI智能分类产品"""
    products = db.query(Product).filter(Product.id.in_(req.product_ids)).all()
    if not products:
        raise HTTPException(status_code=404, detail="未找到产品")

    product_data = []
    for p in products:
        product_data.append(
            f"SKU:{p.sku} | 名称:{p.product_name} | 类目:{p.category} | "
            f"属性:{p.attribute} | 供应商:{p.supplier} | 状态:{p.status}"
        )

    system_prompt = """你是智能分类助手。根据产品信息，为每个产品建议最合适的分类（类目）。
请返回JSON格式（不要加markdown标记）：
{
  "classifications": [
    {"sku": "SKU001", "suggested_category": "建议类目", "confidence": "高/中/低", "reason": "分类理由"},
    ...
  ],
  "summary": "分类总结"
}
注意：如果产品已有类目且合理，保持原类目。"""
    if req.category:
        system_prompt += f"\n请优先归类到「{req.category}」类别下。"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "请分类以下产品:\n" + "\n".join(product_data)},
    ]

    reply = get_ai_response(messages)
    if reply is None:
        # 本地分类
        category_groups = {}
        for p in products:
            cat = p.category or "未分类"
            if cat not in category_groups:
                category_groups[cat] = []
            category_groups[cat].append(p.sku)

        classifications = []
        for cat, skus in category_groups.items():
            for sku in skus:
                classifications.append({
                    "sku": sku,
                    "suggested_category": cat,
                    "confidence": "中",
                    "reason": "保持现有分类",
                })

        return {
            "success": True,
            "classifications": classifications,
            "summary": f"共 {len(products)} 个产品，分布在 {len(category_groups)} 个类目",
            "ai_enabled": False,
        }

    try:
        cleaned = reply.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(cleaned)
        return {"success": True, **parsed, "ai_enabled": True}
    except (json.JSONDecodeError, AttributeError):
        return {"success": True, "classifications": [], "summary": reply, "ai_enabled": True}


@router.post("/summary")
def ai_summary(
    req: AISummaryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """AI生成产品数据总结报告"""
    query = db.query(Product)
    if req.date_range:
        cutoff = datetime.utcnow() - timedelta(days=req.date_range)
        query = query.filter(Product.updated_at >= cutoff)

    total = query.count()
    group_col = getattr(Product, req.group_by, Product.category)

    groups = (
        query.with_entities(group_col, func.count(Product.id))
        .filter(group_col != "", group_col.isnot(None))
        .group_by(group_col)
        .order_by(func.count(Product.id).desc())
        .all()
    )

    # Stats
    low_stock = query.filter(Product.stock_quantity < 10, Product.stock_quantity > 0).count()
    out_of_stock = query.filter(Product.stock_quantity == 0).count()
    total_value = query.with_entities(
        func.sum(Product.purchase_price * Product.purchase_quantity)
    ).scalar() or 0
    pending = query.filter(Product.status == "待采购").count()

    group_summary = f"按「{req.group_by}」分组统计:\n"
    for name, count in groups[:20]:
        group_summary += f"  - {name}: {count}个\n"

    # Try AI for better summary
    system_prompt = f"""你是一个数据分析助手。根据以下采购数据统计，生成一份简洁的总结报告。
用中文回复，涵盖关键发现和 actionable 的建议。保持简洁，突出最重要的数据。"""

    data_summary = (
        f"总产品数: {total}\n"
        f"低库存(<10): {low_stock}\n"
        f"缺货: {out_of_stock}\n"
        f"待采购: {pending}\n"
        f"采购总价值: ¥{float(total_value):.2f}\n\n"
        f"{group_summary}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"数据:\n{data_summary}"},
    ]

    reply = get_ai_response(messages)
    if reply is None:
        reply = (
            f"📊 数据总结\n"
            f"总产品数: {total}\n"
            f"低库存: {low_stock} | 缺货: {out_of_stock} | 待采购: {pending}\n"
            f"采购总价值: ¥{float(total_value):.2f}\n\n"
            f"{group_summary}"
        )

    return {
        "success": True,
        "summary": reply,
        "stats": {
            "total": total,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "pending": pending,
            "total_value": round(float(total_value), 2),
            "groups": [{"name": g[0], "count": g[1]} for g in groups[:20]],
        },
        "ai_enabled": get_openai_client() is not None,
    }