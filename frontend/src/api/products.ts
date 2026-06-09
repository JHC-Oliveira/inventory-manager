import client from './client'

export type Product = {
  id: string
  name: string
  sku: string
  quantity: number
  price: string
  low_stock_threshold: number
  is_active: boolean
}

export type ProductsResponse = {
  items: Product[]
  total: number
  page: number
  page_size: number
}

export const getProducts = async (page = 1, pageSize = 12): Promise<ProductsResponse> => {
  const response = await client.get('/products', {
    params: { page, page_size: pageSize },
  })
  return response.data as ProductsResponse
}