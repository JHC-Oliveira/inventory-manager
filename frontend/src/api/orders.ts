import client from './client'

export type OrderStatus = 'PENDING' | 'FULFILLED' | 'CANCELLED'

export type OrderItem = {
  id: string
  order_id: string
  product_id: string | null
  product_name: string
  product_sku: string
  quantity: number
  unit_price: string
  subtotal: string
  created_at: string
}

export type Order = {
  id: string
  customer_name: string
  status: OrderStatus
  created_by: string | null
  items: OrderItem[]
  created_at: string
  updated_at: string
}

export type OrderListResponse = {
  items: Order[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export type CreateOrderItemPayload = {
  product_id: string
  quantity: number
}

export type CreateOrderPayload = {
  customer_name: string
  items: CreateOrderItemPayload[]
}

export const createOrder = async (data: CreateOrderPayload): Promise<Order> => {
  const response = await client.post('/orders', data)
  return response.data as Order
}

export const cancelOrder = async (orderId: string): Promise<Order> => {
  const response = await client.patch(`/orders/${orderId}/cancel`)
  return response.data as Order
}

export const getOrders = async (
  page = 1,
  pageSize = 10,
): Promise<OrderListResponse> => {
  const response = await client.get('/orders', {
    params: { page, page_size: pageSize },
  })
  return response.data as OrderListResponse
}
