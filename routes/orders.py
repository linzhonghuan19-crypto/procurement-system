from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from database import get_db, PurchaseOrder, OrderItem, User, AuditLog
from auth import get_current_user, require_editor
from datetime import datetime, timezone

router = APIRouter(prefix="/api/orders", tags=["采购单"])


class OrderItemCreate(BaseModel):
    product_id: Optional[int] = None
    product_name: str
    sku: str = ""
    quantity: int = 1
    unit_price: float = 0.0
    remarks: str = ""


class OrderCreate(BaseModel):
    supplier: str = ""
    shipping_cost: float = 0.0
    notes: str = ""
    items: List[OrderItemCreate]


class OrderUpdate(BaseModel):
    supplier: Optional[str] = None
    status: Optional[str] = None
    shipping_cost: Optional[float] = None
    notes: Optional[str] = None


@router.get("")
def list_orders(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(PurchaseOrder)
    if status:
        query = query.filter(PurchaseOrder.status == status)

    total = query.count()
    orders = (
        query.order_by(PurchaseOrder.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": o.id,
                "order_number": o.order_number,
                "supplier": o.supplier,
                "total_amount": o.total_amount,
                "shipping_cost": o.shipping_cost,
                "status": o.status,
                "notes": o.notes,
                "created_by": o.creator.display_name if o.creator else "",
                "approved_by": o.approver.display_name if o.approver else "",
                "item_count": len(o.items),
                "created_at": o.created_at.isoformat() if o.created_at else "",
                "updated_at": o.updated_at.isoformat() if o.updated_at else "",
            }
            for o in orders
        ],
    }


@router.get("/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="采购单不存在")
    return {
        "id": order.id,
        "order_number": order.order_number,
        "supplier": order.supplier,
        "total_amount": order.total_amount,
        "shipping_cost": order.shipping_cost,
        "status": order.status,
        "notes": order.notes,
        "created_by": order.creator.display_name if order.creator else "",
        "approved_by": order.approver.display_name if order.approver else "",
        "created_at": order.created_at.isoformat() if order.created_at else "",
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "product_name": i.product_name,
                "sku": i.sku,
                "quantity": i.quantity,
                "unit_price": i.unit_price,
                "total_price": i.total_price,
                "remarks": i.remarks,
            }
            for i in order.items
        ],
    }


@router.post("")
def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    today = datetime.now(timezone.utc)
    count = db.query(PurchaseOrder).filter(
        PurchaseOrder.created_at >= today.replace(hour=0, minute=0, second=0)
    ).count()
    order_number = f"PO-{today.strftime('%Y%m%d')}-{count + 1:04d}"

    total_amount = sum(
        item.quantity * item.unit_price for item in data.items
    )

    order = PurchaseOrder(
        order_number=order_number,
        supplier=data.supplier,
        total_amount=total_amount,
        shipping_cost=data.shipping_cost,
        notes=data.notes,
        created_by=user.id,
    )
    db.add(order)
    db.flush()

    for item in data.items:
        total_price = item.quantity * item.unit_price
        order_item = OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            product_name=item.product_name,
            sku=item.sku,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=total_price,
            remarks=item.remarks,
        )
        db.add(order_item)

    db.commit()
    db.refresh(order)

    return {
        "id": order.id,
        "order_number": order.order_number,
        "message": "采购单创建成功",
    }


@router.put("/{order_id}")
def update_order(
    order_id: int,
    data: OrderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="采购单不存在")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(order, field, value)
    db.commit()
    return {"message": "更新成功"}


@router.post("/{order_id}/approve")
def approve_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="采购单不存在")
    order.status = "已批准"
    order.approved_by = user.id
    order.approved_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "采购单已批准"}


@router.delete("/{order_id}")
def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="采购单不存在")
    db.delete(order)
    db.commit()
    return {"message": "删除成功"}