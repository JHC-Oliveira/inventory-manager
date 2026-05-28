from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.stock_movement import MovementType


class StockSummaryItem(BaseModel):
    """One row in the stock summary report."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    sku: str
    quantity: int
    price: Decimal
    inventory_value: Decimal
    is_low_stock: bool
    low_stock_threshold: int
    is_active: bool


class StockSummaryResponse(BaseModel):
    """Full stock summary report."""

    model_config = ConfigDict(from_attributes=True)

    items: list[StockSummaryItem]
    total_inventory_value: Decimal
    total_products: int


class LowStockItem(BaseModel):
    """One row in the low-stock report."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    sku: str
    quantity: int
    low_stock_threshold: int
    is_low_stock: bool
    is_active: bool


class LowStockResponse(BaseModel):
    """Full low-stock report."""

    model_config = ConfigDict(from_attributes=True)

    items: list[LowStockItem]
    total: int


class TopProductItem(BaseModel):
    """One row in the top-products report."""

    model_config = ConfigDict(from_attributes=True)

    product_sku: str
    product_name: str
    total_quantity: int
    total_orders: int
    total_revenue: Decimal


class TopProductsResponse(BaseModel):
    """Full top-products report."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TopProductItem]
    total: int


class MovementHistoryItem(BaseModel):
    """One row in the movement history analytics report."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str | None
    product_sku: str
    movement_type: MovementType
    quantity_change: int
    quantity_before: int
    quantity_after: int
    note: str | None
    created_by: str | None
    created_at: datetime


class MovementHistoryResponse(BaseModel):
    """Full movement history analytics report."""

    model_config = ConfigDict(from_attributes=True)

    items: list[MovementHistoryItem]
    total: int
    page: int
    page_size: int
    total_pages: int