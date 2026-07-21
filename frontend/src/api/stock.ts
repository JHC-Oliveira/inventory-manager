import client from './client'

export type MovementType = 'RECEIVE' | 'SHIP' | 'ADJUST'

export type StockMovement = {
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

export type StockMovementListResponse = {
  items: StockMovement[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export type StockAdjustPayload = {
  movement_type: MovementType
  quantity_change: number
  note?: string
}

export const adjustStock = async (
  productId: string,
  data: StockAdjustPayload
): Promise<StockMovement> => {
  const response = await client.post(`/stock/${productId}/adjust`, data)
  return response.data as StockMovement
}

export const getStockHistory = async (
  productId: string,
  page = 1,
  pageSize = 10
): Promise<StockMovementListResponse> => {
  const response = await client.get(`/stock/${productId}/history`, {
    params: { page, page_size: pageSize },
  })
  return response.data as StockMovementListResponse
}
