from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING  

from sqlalchemy import (
    Boolean, DateTime, ForeignKey,
    Integer, Numeric, String, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.utils.id_generator import make_id 

if TYPE_CHECKING:
    from app.models.user import User  

class Product(Base):
    __tablename__ = "products"

    # --- Identity ---
    id: Mapped[str] = mapped_column(
        String(40),
        primary_key=True,
        default=lambda: make_id("prd")
    )
    sku: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True           # every lookup by SKU is instant
    )

    # --- Details ---
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Money & Stock ---
    price: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    low_stock_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10           # alert when stock drops below this
    )

    # --- Status ---
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    # --- Ownership ---
    created_by: Mapped[str | None] = mapped_column(
        String(40),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True        # if admin user is deleted, product survives
    )

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)  # auto-updates on every change
    )

    # --- Relationships ---
    creator: Mapped["User"] = relationship("User", backref="products")

    # --- Computed property ---
    @property
    def is_low_stock(self) -> bool:
        """True when stock is at or below the alert threshold."""
        return self.quantity <= self.low_stock_threshold

    def __repr__(self) -> str:
        return f"<Product id={self.id} sku={self.sku} qty={self.quantity}>"