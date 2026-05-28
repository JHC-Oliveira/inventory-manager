from datetime import date

from fastapi import APIRouter, Depends, Query

from app.database import get_db
from app.dependencies.auth import get_current_admin
from app.schemas.report import (
    LowStockResponse,
    MovementHistoryResponse,
    StockSummaryResponse,
    TopProductsResponse,
)
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/stock-summary", response_model=StockSummaryResponse)
async def stock_summary(
    db=Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    service = ReportService(db)
    return await service.get_stock_summary()


@router.get("/low-stock", response_model=LowStockResponse)
async def low_stock(
    db=Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    service = ReportService(db)
    return await service.get_low_stock()


@router.get("/top-products", response_model=TopProductsResponse)
async def top_products(
    db=Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    service = ReportService(db)
    return await service.get_top_products()


@router.get("/movement-history", response_model=MovementHistoryResponse)
async def movement_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db=Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    service = ReportService(db)
    return await service.get_movement_history(
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
    )