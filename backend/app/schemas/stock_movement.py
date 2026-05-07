from datetime import datetime
from pydantic import BaseModel, field_validator, model_validator
from app.models.stock_movement import MovementType


class StockAdjustRequest(BaseModel):
    """What the client sends to POST /stock/{product_id}/adjust"""

    movement_type: MovementType
    quantity_change: int
    note: str | None = None

    @field_validator("quantity_change")
    @classmethod
    def quantity_change_not_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("quantity_change cannot be zero")
        return v

    @model_validator(mode="after")
    def ship_and_adjust_must_be_negative_or_positive(self) -> "StockAdjustRequest":
        """
        RECEIVE must always be positive  — you can't receive -10 units
        SHIP    must always be negative  — you're removing stock
        ADJUST  can be either            — correction up or down
        """
        if self.movement_type == MovementType.RECEIVE and self.quantity_change < 0:
            raise ValueError("RECEIVE movements must have a positive quantity_change")
        if self.movement_type == MovementType.SHIP and self.quantity_change > 0:
            raise ValueError("SHIP movements must have a negative quantity_change")
        return self


class StockMovementResponse(BaseModel):
    """Shape of a single movement record returned to the client"""

    id: str
    product_id: str
    movement_type: MovementType
    quantity_change: int
    quantity_before: int
    quantity_after: int
    note: str | None
    created_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class StockMovementListResponse(BaseModel):
    """Paginated list of movements for a product"""

    items: list[StockMovementResponse]
    total: int
    page: int
    page_size: int
    total_pages: int