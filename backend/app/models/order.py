import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User


class OrderStatus(PyEnum):
    PENDING = "pending"          # order placed, stock reserved
    FULFILLED = "fulfilled"      # order shipped / completed
    CANCELLED = "cancelled"      # order cancelled, stock restored


class Order(Base):
    __tablename__ = "orders"

    # --- Identity ---
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Details ---
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # --- Status ---
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), nullable=False, default=OrderStatus.PENDING
    )

    # --- Ownership ---
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # --- Relationships ---
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
    creator: Mapped["User"] = relationship("User", backref="orders")

    def __repr__(self) -> str:
        return f"Order id={self.id} status={self.status.value}"


class OrderItem(Base):
    __tablename__ = "order_items"

    # --- Identity ---
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- Foreign Keys ---
    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="CASCADE"),  # item dies with order
        nullable=False,
        index=True,
    )
    product_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("products.id", ondelete="SET NULL"),  # history survives
        nullable=True,
        index=True,
    )
    
    # --- Product snapshot (locked at order time) ---      
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_sku: Mapped[str] = mapped_column(String(100), nullable=False)

    # --- Quantity & Price snapshot ---
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2), nullable=False
    )  # price locked at time of order, never updated

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # --- Relationships ---
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product", backref="order_items")

    @property
    def subtotal(self) -> Decimal:
        """Computed: quantity × unit_price. Never stored — derived on read."""
        return Decimal(str(self.quantity)) * self.unit_price

    def __repr__(self) -> str:
        return f"OrderItem order={self.order_id} product={self.product_id} qty={self.quantity}"