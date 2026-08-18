from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel
from typing import Optional, List
from database import get_db, Product, User, AuditLog, ProductStatus
from auth import get_current_user, require_editor
from datetime import datetime, timezone

router = APIRouter(prefix="/api/products", tags=["产品"])


class ProductCreate(BaseModel):
    sku: str
    product_name: str
    category: str = ""
    purchase_link: str = ""
    image_url: str = ""
    price_1688: float = 0.0
    price_amazon: float = 0.0
    price_selling: float = 0.0
    supplier: str = ""
    supplier_link: str = ""
    stock_quantity: int = 0
    warehouse_location: str = ""
    moq: int = 0
    status: str = "待采购"
    remarks: str = ""


class ProductUpdate(BaseModel):
    product_name: Optional[str] = None
    category: Optional[str] = None
    purchase_link: Optional[str] = None
    image_url: Optional[str] = None
    price_1688: Optional[float] = None
    price_amazon: Optional[float] = None
    price_selling: Optional[float] = None
    supplier: Optional[str] = None
    supplier_link: Optional[str] = None
    stock_quantity: Optional[int] = None
    warehouse_location: Optional[str] = None
    moq: Optional[int] = None
    status: Optional[str] = None
    remarks: Optional[str] = None


@router.get("")
def list_products(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Product)
    if search:
        query = query.filter(
            or_(
                Product.sku.ilike(f"%{search}%"),
                Product.product_name.ilike(f"%{search}%"),
                Product.supplier.ilike(f"%{search}%"),
            )
        )
    if status:
        query = query.filter(Product.status == status)
    if category:
        query = query.filter(Product.category == category)

    total = query.count()
    products = (
        query.order_by(Product.updated_at.desc())
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
                "id": p.id,
                "sku": p.sku,
                "product_name": p.product_name,
                "category": p.category,
                "purchase_link": p.purchase_link,
                "image_url": p.image_url,
                "price_1688": p.price_1688,
                "price_amazon": p.price_amazon,
                "price_selling": p.price_selling,
                "supplier": p.supplier,
                "supplier_link": p.supplier_link,
                "stock_quantity": p.stock_quantity,
                "warehouse_location": p.warehouse_location,
                "moq": p.moq,
                "status": p.status,
                "remarks": p.remarks,
                "created_by": p.creator.display_name if p.creator else "",
                "updated_by": p.updater.display_name if p.updater else "",
                "created_at": p.created_at.isoformat() if p.created_at else "",
                "updated_at": p.updated_at.isoformat() if p.updated_at else "",
            }
            for p in products
        ],
    }


@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(Product.category).distinct().all()
    return [c[0] for c in categories if c[0]]


@router.get("/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    return {
        "id": product.id,
        "sku": product.sku,
        "product_name": product.product_name,
        "category": product.category,
        "purchase_link": product.purchase_link,
        "image_url": product.image_url,
        "price_1688": product.price_1688,
        "price_amazon": product.price_amazon,
        "price_selling": product.price_selling,
        "supplier": product.supplier,
        "supplier_link": product.supplier_link,
        "stock_quantity": product.stock_quantity,
        "warehouse_location": product.warehouse_location,
        "moq": product.moq,
        "status": product.status,
        "remarks": product.remarks,
    }


@router.post("")
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    existing = db.query(Product).filter(Product.sku == data.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail="SKU已存在")

    product = Product(
        sku=data.sku,
        product_name=data.product_name,
        category=data.category,
        purchase_link=data.purchase_link,
        image_url=data.image_url,
        price_1688=data.price_1688,
        price_amazon=data.price_amazon,
        price_selling=data.price_selling,
        supplier=data.supplier,
        supplier_link=data.supplier_link,
        stock_quantity=data.stock_quantity,
        warehouse_location=data.warehouse_location,
        moq=data.moq,
        status=data.status,
        remarks=data.remarks,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    log = AuditLog(user_id=user.id, action="create", target_type="product", target_id=product.id,
                   details=f"创建产品 {product.sku}")
    db.add(log)
    db.commit()

    return {"id": product.id, "sku": product.sku, "message": "创建成功"}


@router.put("/{product_id}")
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(product, field, value)
    product.updated_by = user.id
    product.updated_at = datetime.now(timezone.utc)
    db.commit()

    log = AuditLog(user_id=user.id, action="update", target_type="product", target_id=product.id,
                   details=f"更新产品 {product.sku}: {list(update_data.keys())}")
    db.add(log)
    db.commit()

    return {"message": "更新成功"}


@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    db.delete(product)
    db.commit()
    return {"message": "删除成功"}


@router.post("/batch")
def batch_create(
    products: List[ProductCreate],
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    created = []
    for data in products:
        existing = db.query(Product).filter(Product.sku == data.sku).first()
        if existing:
            continue
        product = Product(
            sku=data.sku, product_name=data.product_name, category=data.category,
            purchase_link=data.purchase_link, image_url=data.image_url,
            price_1688=data.price_1688, price_amazon=data.price_amazon,
            price_selling=data.price_selling, supplier=data.supplier,
            supplier_link=data.supplier_link, stock_quantity=data.stock_quantity,
            warehouse_location=data.warehouse_location, moq=data.moq,
            status=data.status, remarks=data.remarks,
            created_by=user.id, updated_by=user.id,
        )
        db.add(product)
        created.append(data.sku)
    db.commit()
    return {"message": f"成功创建 {len(created)} 个产品", "created": created}


@router.post("/import")
def import_from_wecom(
    products: List[ProductCreate],
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    """从企业微信表格导入数据"""
    imported = 0
    updated = 0
    for data in products:
        existing = db.query(Product).filter(Product.sku == data.sku).first()
        if existing:
            for field, value in data.model_dump(exclude_unset=True).items():
                if value:
                    setattr(existing, field, value)
            existing.updated_by = user.id
            updated += 1
        else:
            product = Product(
                sku=data.sku, product_name=data.product_name, category=data.category,
                purchase_link=data.purchase_link, image_url=data.image_url,
                price_1688=data.price_1688, price_amazon=data.price_amazon,
                price_selling=data.price_selling, supplier=data.supplier,
                supplier_link=data.supplier_link, stock_quantity=data.stock_quantity,
                warehouse_location=data.warehouse_location, moq=data.moq,
                status=data.status, remarks=data.remarks,
                created_by=user.id, updated_by=user.id,
            )
            db.add(product)
            imported += 1
    db.commit()
    return {"message": f"导入完成: 新增{imported}, 更新{updated}"}