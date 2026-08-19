"""Dashboard data API - 仪表盘数据"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db, Product
from auth import get_current_user, User

router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


@router.get("/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get dashboard statistics"""
    total = db.query(Product).count()

    # Category distribution
    categories = (
        db.query(Product.category, func.count(Product.id))
        .filter(Product.category != "", Product.category.isnot(None))
        .group_by(Product.category)
        .order_by(func.count(Product.id).desc())
        .limit(20)
        .all()
    )

    # Status distribution
    statuses = (
        db.query(Product.status, func.count(Product.id))
        .filter(Product.status != "", Product.status.isnot(None))
        .group_by(Product.status)
        .all()
    )

    # Attribute distribution
    attributes = (
        db.query(Product.attribute, func.count(Product.id))
        .filter(Product.attribute != "", Product.attribute.isnot(None))
        .group_by(Product.attribute)
        .order_by(func.count(Product.id).desc())
        .all()
    )

    # Low stock products
    low_stock = (
        db.query(Product)
        .filter(Product.stock_quantity < 10, Product.stock_quantity > 0)
        .count()
    )
    out_of_stock = (
        db.query(Product)
        .filter(Product.stock_quantity == 0)
        .count()
    )

    # Total purchase value
    total_value = (
        db.query(func.sum(Product.purchase_price * Product.purchase_quantity))
        .scalar() or 0
    )

    # Supplier count
    supplier_count = (
        db.query(Product.supplier)
        .filter(Product.supplier != "", Product.supplier.isnot(None))
        .distinct()
        .count()
    )

    return {
        "total_products": total,
        "low_stock": low_stock,
        "out_of_stock": out_of_stock,
        "total_value": round(float(total_value), 2),
        "supplier_count": supplier_count,
        "categories": [
            {"name": c[0] or "未分类", "count": c[1]} for c in categories
        ],
        "statuses": [
            {"name": s[0] or "未知", "count": s[1]} for s in statuses
        ],
        "attributes": [
            {"name": a[0] or "未分类", "count": a[1]} for a in attributes
        ],
    }