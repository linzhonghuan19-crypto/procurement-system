from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel
from typing import Optional, List
from database import get_db, Product, User, AuditLog, ProductStatus
from auth import get_current_user, require_editor, require_admin
from datetime import datetime, timezone
import zipfile, xml.etree.ElementTree as ET, io, math

router = APIRouter(prefix="/api/products", tags=["产品"])


class ProductCreate(BaseModel):
    date: str = ""
    attribute: str = ""
    category: str = ""
    store: str = ""
    mercadolibre_link: str = ""
    purchase_link: str = ""
    sku: str
    product_name: str
    product_attributes: str = ""
    purchase_remarks: str = ""
    purchase_quantity: int = 0
    warehouse_remarks: str = ""
    order_number: str = ""
    purchase_price: float = 0.0
    new_purchase_price: float = 0.0
    new_purchase_link: str = ""
    supplier: str = ""
    image_url: str = ""
    stock_quantity: int = 0
    remark1: str = ""
    remark2: str = ""
    remark3: str = ""
    remark4: str = ""
    length: float = 0.0
    width: float = 0.0
    height: float = 0.0
    status: str = "待采购"
    # 旧字段兼容
    price_1688: float = 0.0
    price_amazon: float = 0.0
    price_selling: float = 0.0
    supplier_link: str = ""
    warehouse_location: str = ""
    moq: int = 0
    remarks: str = ""


class ProductUpdate(BaseModel):
    date: Optional[str] = None
    attribute: Optional[str] = None
    category: Optional[str] = None
    store: Optional[str] = None
    mercadolibre_link: Optional[str] = None
    purchase_link: Optional[str] = None
    product_name: Optional[str] = None
    product_attributes: Optional[str] = None
    purchase_remarks: Optional[str] = None
    purchase_quantity: Optional[int] = None
    warehouse_remarks: Optional[str] = None
    order_number: Optional[str] = None
    purchase_price: Optional[float] = None
    new_purchase_price: Optional[float] = None
    new_purchase_link: Optional[str] = None
    supplier: Optional[str] = None
    image_url: Optional[str] = None
    stock_quantity: Optional[int] = None
    remark1: Optional[str] = None
    remark2: Optional[str] = None
    remark3: Optional[str] = None
    remark4: Optional[str] = None
    length: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    status: Optional[str] = None
    # 旧字段兼容
    price_1688: Optional[float] = None
    price_amazon: Optional[float] = None
    price_selling: Optional[float] = None
    supplier_link: Optional[str] = None
    warehouse_location: Optional[str] = None
    moq: Optional[int] = None
    remarks: Optional[str] = None


@router.get("")
def list_products(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=10000),
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
                "date": p.date,
                "attribute": p.attribute,
                "category": p.category,
                "store": p.store,
                "mercadolibre_link": p.mercadolibre_link,
                "purchase_link": p.purchase_link,
                "sku": p.sku,
                "product_name": p.product_name,
                "product_attributes": p.product_attributes,
                "purchase_remarks": p.purchase_remarks,
                "purchase_quantity": p.purchase_quantity,
                "warehouse_remarks": p.warehouse_remarks,
                "order_number": p.order_number,
                "purchase_price": p.purchase_price,
                "new_purchase_price": p.new_purchase_price,
                "new_purchase_link": p.new_purchase_link,
                "supplier": p.supplier,
                "image_url": p.image_url,
                "stock_quantity": p.stock_quantity,
                "remark1": p.remark1,
                "remark2": p.remark2,
                "remark3": p.remark3,
                "remark4": p.remark4,
                "length": p.length,
                "width": p.width,
                "height": p.height,
                "status": p.status,
                "price_1688": p.price_1688,
                "price_amazon": p.price_amazon,
                "price_selling": p.price_selling,
                "supplier_link": p.supplier_link,
                "warehouse_location": p.warehouse_location,
                "moq": p.moq,
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
        "date": product.date,
        "attribute": product.attribute,
        "category": product.category,
        "store": product.store,
        "mercadolibre_link": product.mercadolibre_link,
        "purchase_link": product.purchase_link,
        "sku": product.sku,
        "product_name": product.product_name,
        "product_attributes": product.product_attributes,
        "purchase_remarks": product.purchase_remarks,
        "purchase_quantity": product.purchase_quantity,
        "warehouse_remarks": product.warehouse_remarks,
        "order_number": product.order_number,
        "purchase_price": product.purchase_price,
        "new_purchase_price": product.new_purchase_price,
        "new_purchase_link": product.new_purchase_link,
        "supplier": product.supplier,
        "image_url": product.image_url,
        "stock_quantity": product.stock_quantity,
        "remark1": product.remark1,
        "remark2": product.remark2,
        "remark3": product.remark3,
        "remark4": product.remark4,
        "length": product.length,
        "width": product.width,
        "height": product.height,
        "status": product.status,
        "price_1688": product.price_1688,
        "price_amazon": product.price_amazon,
        "price_selling": product.price_selling,
        "supplier_link": product.supplier_link,
        "warehouse_location": product.warehouse_location,
        "moq": product.moq,
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
        date=data.date, attribute=data.attribute, category=data.category,
        store=data.store, mercadolibre_link=data.mercadolibre_link,
        purchase_link=data.purchase_link, sku=data.sku, product_name=data.product_name,
        product_attributes=data.product_attributes, purchase_remarks=data.purchase_remarks,
        purchase_quantity=data.purchase_quantity, warehouse_remarks=data.warehouse_remarks,
        order_number=data.order_number, purchase_price=data.purchase_price,
        new_purchase_price=data.new_purchase_price, new_purchase_link=data.new_purchase_link,
        supplier=data.supplier, image_url=data.image_url, stock_quantity=data.stock_quantity,
        remark1=data.remark1, remark2=data.remark2, remark3=data.remark3, remark4=data.remark4,
        length=data.length, width=data.width, height=data.height,
        status=data.status,
        price_1688=data.price_1688, price_amazon=data.price_amazon, price_selling=data.price_selling,
        supplier_link=data.supplier_link, warehouse_location=data.warehouse_location,
        moq=data.moq, remarks=data.remarks,
        created_by=user.id, updated_by=user.id,
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
            date=data.date, attribute=data.attribute, category=data.category,
            store=data.store, mercadolibre_link=data.mercadolibre_link,
            purchase_link=data.purchase_link, sku=data.sku, product_name=data.product_name,
            product_attributes=data.product_attributes, purchase_remarks=data.purchase_remarks,
            purchase_quantity=data.purchase_quantity, warehouse_remarks=data.warehouse_remarks,
            order_number=data.order_number, purchase_price=data.purchase_price,
            new_purchase_price=data.new_purchase_price, new_purchase_link=data.new_purchase_link,
            supplier=data.supplier, image_url=data.image_url, stock_quantity=data.stock_quantity,
            remark1=data.remark1, remark2=data.remark2, remark3=data.remark3, remark4=data.remark4,
            length=data.length, width=data.width, height=data.height,
            status=data.status,
            price_1688=data.price_1688, price_amazon=data.price_amazon, price_selling=data.price_selling,
            supplier_link=data.supplier_link, warehouse_location=data.warehouse_location,
            moq=data.moq, remarks=data.remarks,
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
                date=data.date, attribute=data.attribute, category=data.category,
                store=data.store, mercadolibre_link=data.mercadolibre_link,
                purchase_link=data.purchase_link, sku=data.sku, product_name=data.product_name,
                product_attributes=data.product_attributes, purchase_remarks=data.purchase_remarks,
                purchase_quantity=data.purchase_quantity, warehouse_remarks=data.warehouse_remarks,
                order_number=data.order_number, purchase_price=data.purchase_price,
                new_purchase_price=data.new_purchase_price, new_purchase_link=data.new_purchase_link,
                supplier=data.supplier, image_url=data.image_url, stock_quantity=data.stock_quantity,
                remark1=data.remark1, remark2=data.remark2, remark3=data.remark3, remark4=data.remark4,
                length=data.length, width=data.width, height=data.height,
                status=data.status,
                price_1688=data.price_1688, price_amazon=data.price_amazon, price_selling=data.price_selling,
                supplier_link=data.supplier_link, warehouse_location=data.warehouse_location,
                moq=data.moq, remarks=data.remarks,
                created_by=user.id, updated_by=user.id,
            )
            db.add(product)
            imported += 1
    db.commit()
    return {"message": f"导入完成: 新增{imported}, 更新{updated}"}


@router.post("/upload-excel")
def upload_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    """Upload an Excel (.xlsx) file and import its data"""
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 文件")

    content = file.file.read()

    field_map = {
        '日期': 'date', '属性': 'attribute', '组别': 'category',
        '店铺': 'store', '美客多产品链接': 'mercadolibre_link',
        '原采购链接': 'purchase_link', 'SKU': 'sku',
        '标题': 'product_name', '产品属性': 'product_attributes',
        '采购备注': 'purchase_remarks', '采购数量': 'purchase_quantity',
        '仓库备注': 'warehouse_remarks', '订单号': 'order_number',
        '采购价RMB': 'purchase_price', '新采购价RMB': 'new_purchase_price',
        '新采购链接': 'new_purchase_link', '供应商': 'supplier',
        '图片': 'image_url', '库存': 'stock_quantity',
        '备注1': 'remark1', '备注2': 'remark2', '备注3': 'remark3',
        '备注4': 'remark4', '长': 'length', '宽': 'width', '高': 'height',
    }

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            ss = ET.fromstring(z.read('xl/sharedStrings.xml'))
            strs = []
            ns2 = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            for si in ss.findall('.//s:si', ns2):
                texts = []
                for t in si.findall('.//s:t', ns2):
                    if t.text:
                        texts.append(t.text)
                strs.append(''.join(texts))

            sheet1 = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
            rows = sheet1.findall('.//s:row', ns2)
            if len(rows) < 2:
                raise HTTPException(status_code=400, detail="Excel文件没有数据行")

            # Parse headers
            headers = []
            for c in rows[0].findall('s:c', ns2):
                v = c.find('s:v', ns2)
                val = v.text if v is not None else ''
                t = c.get('t')
                if t == 's' and val:
                    idx = int(val)
                    if idx < len(strs):
                        val = strs[idx]
                headers.append(val.strip())

            while headers and headers[-1] == '':
                headers.pop()

            imported = 0
            updated = 0

            for row in rows[1:]:
                cells = row.findall('s:c', ns2)
                item = {}
                for i, c in enumerate(cells):
                    v = c.find('s:v', ns2)
                    val = v.text if v is not None else ''
                    t = c.get('t')
                    if t == 's' and val:
                        idx = int(val)
                        if idx < len(strs):
                            val = strs[idx]
                    if i < len(headers):
                        field = field_map.get(headers[i])
                        if field:
                            if field in ('purchase_quantity', 'stock_quantity'):
                                try:
                                    val = int(float(val))
                                except (ValueError, TypeError):
                                    val = 0
                            elif field in ('purchase_price', 'new_purchase_price', 'length', 'width', 'height'):
                                try:
                                    val = float(val)
                                except (ValueError, TypeError):
                                    val = 0.0
                            item[field] = val

                if not item.get('sku') and not item.get('product_name'):
                    continue
                if not item.get('sku'):
                    item['sku'] = f"AUTO-{item.get('product_name', 'unknown')[:20]}"
                if not item.get('product_name'):
                    item['product_name'] = item['sku']

                existing = db.query(Product).filter(Product.sku == item['sku']).first()
                if existing:
                    for field, value in item.items():
                        if value:
                            setattr(existing, field, value)
                    existing.updated_by = user.id
                    updated += 1
                else:
                    product = Product(
                        date=item.get('date', ''),
                        attribute=item.get('attribute', ''),
                        category=item.get('category', ''),
                        store=item.get('store', ''),
                        mercadolibre_link=item.get('mercadolibre_link', ''),
                        purchase_link=item.get('purchase_link', ''),
                        sku=item['sku'],
                        product_name=item['product_name'],
                        product_attributes=item.get('product_attributes', ''),
                        purchase_remarks=item.get('purchase_remarks', ''),
                        purchase_quantity=item.get('purchase_quantity', 0),
                        warehouse_remarks=item.get('warehouse_remarks', ''),
                        order_number=item.get('order_number', ''),
                        purchase_price=item.get('purchase_price', 0.0),
                        new_purchase_price=item.get('new_purchase_price', 0.0),
                        new_purchase_link=item.get('new_purchase_link', ''),
                        supplier=item.get('supplier', ''),
                        image_url=item.get('image_url', ''),
                        stock_quantity=item.get('stock_quantity', 0),
                        remark1=item.get('remark1', ''),
                        remark2=item.get('remark2', ''),
                        remark3=item.get('remark3', ''),
                        remark4=item.get('remark4', ''),
                        length=item.get('length', 0.0),
                        width=item.get('width', 0.0),
                        height=item.get('height', 0.0),
                        status="待采购",
                        created_by=user.id,
                        updated_by=user.id,
                    )
                    db.add(product)
                    imported += 1

            db.commit()
            return {"message": f"导入完成: 新增{imported}, 更新{updated}", "imported": imported, "updated": updated}

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="文件格式错误，请上传有效的 .xlsx 文件")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析失败: {str(e)}")