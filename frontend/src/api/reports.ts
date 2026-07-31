import client from './client'
import type { MovementType } from './stock'

export type StockSummaryItem = {
  id: string
  name: string
  sku: string
  quantity: number
  price: string
  inventory_value: string
  is_low_stock: boolean
  low_stock_threshold: number
  is_active: boolean
}

export type StockSummaryResponse = {
  items: StockSummaryItem[]
  total_inventory_value: string
  total_products: number
}

export type LowStockItem = {
  id: string
  name: string
  sku: string
  quantity: number
  low_stock_threshold: number
  is_low_stock: boolean
  is_active: boolean
}

export type LowStockResponse = {
  items: LowStockItem[]
  total: number
}

export type TopProductItem = {
  product_sku: string
  product_name: string
  total_quantity: number
  total_orders: number
  total_revenue: string
}

export type TopProductsResponse = {
  items: TopProductItem[]
  total: number
}

export type MovementHistoryItem = {
  id: string
  product_id: string | null
  product_sku: string
  movement_type: MovementType
  quantity_change: number
  quantity_before: number
  quantity_after: number
  note: string | null
  created_by: string | null
  created_at: string
}

export type MovementHistoryResponse = {
  items: MovementHistoryItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export const getStockSummary = async (): Promise<StockSummaryResponse> => {
  const response = await client.get('/reports/stock-summary')
  return response.data as StockSummaryResponse
}

export const getLowStock = async (): Promise<LowStockResponse> => {
  const response = await client.get('/reports/low-stock')
  return response.data as LowStockResponse
}

export const getTopProducts = async (): Promise<TopProductsResponse> => {
  const response = await client.get('/reports/top-products')
  return response.data as TopProductsResponse
}

export const getMovementHistory = async (
  page = 1,
  pageSize = 10,
  startDate?: string,
  endDate?: string,
): Promise<MovementHistoryResponse> => {
  const response = await client.get('/reports/movement-history', {
    params: {
      page,
      page_size: pageSize,
      ...(startDate && { start_date: startDate }),
      ...(endDate && { end_date: endDate }),
    },
  })
  return response.data as MovementHistoryResponse
}
