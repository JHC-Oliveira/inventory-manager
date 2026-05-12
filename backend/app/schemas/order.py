from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.models.order import OrderStatus


# ---------------------------------------------------------------------------
# REQUEST schemas  (client → API)
# ---------------------------------------------------------------------------

class OrderItemCreate(BaseModel):
    """One line item inside a new order request."""

    product_id: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)  # must be at least 1


class OrderCreate(BaseModel):
    """What the client sends to POST /orders."""

    customer_name: str = Field(..., min_length=1, max_length=255)
    items: list[OrderItemCreate] = Field(..., min_length=1)
    # min_length=1 → an order with zero items is meaningless, reject it

    @model_validator(mode="after")
    def no_duplicate_products(self) -> "OrderCreate":
        """
        Reject orders where the same product_id appears more than once.
        The client should send one line item with quantity=5,
        not five line items with quantity=1 each.
        """
        seen = set()
        for item in self.items:
            if item.product_id in seen:
                raise ValueError(
                    f"Duplicate product_id {item.product_id!r} in order. "
                    "Combine duplicate items into a single line."
                )
            seen.add(item.product_id)
        return self


# ---------------------------------------------------------------------------
# RESPONSE schemas  (API → client)
# ---------------------------------------------------------------------------

class OrderItemResponse(BaseModel):
    """Shape of a single order line item returned to the client."""

    id: str
    order_id: str
    product_id: Optional[str]         # may be None if product was hard-deleted
    product_name: str                  # snapshot — always available
    product_sku: str                   # snapshot — always available
    quantity: int
    unit_price: Decimal
    subtotal: Decimal                  # computed @property on the model
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    """Shape of a full order with its line items returned to the client."""

    id: str
    customer_name: str
    status: OrderStatus
    created_by: Optional[str]
    items: list[OrderItemResponse]     # always returned with the order
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    """Paginated list of orders."""

    items: list[OrderResponse]
    total: int
    page: int
    page_size: int
    total_pages: int