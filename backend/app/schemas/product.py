from decimal import Decimal
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

# Sentinel — a unique object that means "this field was not sent at all"
UNSET = object()

class ProductCreate(BaseModel):
    """Schema for creating a new product — what the client sends."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    sku: str = Field(..., min_length=1, max_length=100)
    price: Decimal = Field(..., gt=0, decimal_places=2)
    quantity: int = Field(default=0, ge=0)
    low_stock_threshold: int = Field(default=10, ge=0)

    @field_validator("sku")
    @classmethod
    def sku_uppercase(cls, v: str) -> str:
        """SKUs are always stored uppercase — TSHIRT-BLU-L not tshirt-blu-l."""
        return v.upper().strip()

    @field_validator("name")
    @classmethod
    def name_strip(cls, v: str) -> str:
        """Remove accidental leading/trailing whitespace."""
        return v.strip()


class ProductUpdate(BaseModel):
    """Schema for updating a product — all fields optional (PATCH style)."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    price: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    quantity: Optional[int] = Field(None, ge=0)
    low_stock_threshold: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def name_strip(cls, v: str | None) -> str | None:
        if v is not None:
            return v.strip()
        return v


class ProductResponse(BaseModel):
    """Schema for returning product data — what the API sends back."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str]
    sku: str
    price: Decimal
    quantity: int
    low_stock_threshold: int
    is_low_stock: bool
    is_active: bool
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    """Schema for returning a paginated list of products."""
    model_config = ConfigDict(from_attributes=True)

    items: list[ProductResponse]
    total: int
    page: int
    page_size: int
    total_pages: int