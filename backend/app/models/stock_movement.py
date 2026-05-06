import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from app.database import Base

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
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    product_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", backref="movements")
    creator: Mapped["User"] = relationship("User", backref="stock_movements")