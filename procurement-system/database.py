from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone
import enum

SQLALCHEMY_DATABASE_URL = "sqlite:///./procurement.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ProductStatus(str, enum.Enum):
    PENDING = "待采购"
    ORDERED = "已下单"
    IN_TRANSIT = "在途"
    WAREHOUSED = "已入库"
    DISCONTINUED = "停售"


class OrderStatus(str, enum.Enum):
    PENDING_APPROVAL = "待审核"
    APPROVED = "已批准"
    ORDERED = "已下单"
    RECEIVED = "已收货"
    CANCELLED = "已取消"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100))
    role = Column(String(20), default=UserRole.EDITOR.value)
    wecom_user_id = Column(String(100), nullable=True)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(100), unique=True, index=True, nullable=False)
    product_name = Column(String(500), nullable=False)
    category = Column(String(200), default="")
    purchase_link = Column(Text, default="")
    image_url = Column(Text, default="")
    price_1688 = Column(Float, default=0.0)
    price_amazon = Column(Float, default=0.0)
    price_selling = Column(Float, default=0.0)
    supplier = Column(String(200), default="")
    supplier_link = Column(Text, default="")
    stock_quantity = Column(Integer, default=0)
    warehouse_location = Column(String(200), default="")
    moq = Column(Integer, default=0, comment="最小起订量")
    status = Column(String(20), default=ProductStatus.PENDING.value)
    remarks = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    creator = relationship("User", foreign_keys=[created_by], lazy="joined")
    updater = relationship("User", foreign_keys=[updated_by], lazy="joined")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(100), unique=True, index=True, nullable=False)
    supplier = Column(String(200), default="")
    total_amount = Column(Float, default=0.0)
    status = Column(String(20), default=OrderStatus.PENDING_APPROVAL.value)
    shipping_cost = Column(Float, default=0.0)
    notes = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    creator = relationship("User", foreign_keys=[created_by], lazy="joined")
    approver = relationship("User", foreign_keys=[approved_by], lazy="joined")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    product_name = Column(String(500), nullable=False)
    sku = Column(String(100), default="")
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, default=0.0)
    total_price = Column(Float, default=0.0)
    remarks = Column(Text, default="")

    order = relationship("PurchaseOrder", back_populates="items")
    product = relationship("Product", lazy="joined")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(50), nullable=False)
    target_type = Column(String(50))
    target_id = Column(Integer)
    details = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()