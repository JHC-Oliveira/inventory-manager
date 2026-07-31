from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.id_generator import make_id

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User
    


class MovementType(PyEnum):
    RECEIVE  = "RECEIVE"   # stock arriving — purchase order, supplier delivery
    SHIP     = "SHIP"      # stock leaving  — customer order fulfilled
    ADJUST   = "ADJUST"    # manual correction — damage, recount, write-off


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: make_id("stk")
    )
    
    # --- FK is now nullable + SET NULL ---
    product_id: Mapped[str | None] = mapped_column(
        String(40),
        ForeignKey("products.id", ondelete="SET NULL"),  
        nullable=True,                                    
        index=True,
    )
    
    # --- Product snapshot (NEW) ---
    product_sku: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    
    movement_type: Mapped[MovementType] = mapped_column(
        Enum(MovementType), nullable=False
    )
    quantity_change: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    quantity_before: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    quantity_after: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    note: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(
        String(40),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", backref="movements")
    creator: Mapped["User"] = relationship("User", backref="stock_movements")