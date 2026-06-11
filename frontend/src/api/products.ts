import client from './client'

export type Product = {
  id: string
  name: string
  description: string | null
  sku: string
  price: number          
  quantity: number
  low_stock_threshold: number
  is_low_stock: boolean   
  is_active: boolean
  created_by: string | null
  created_at: string
  updated_at: string
}

export type ProductsResponse = {
  items: Product[]
  total: number
  page: number
  page_size: number
}

export type CreateProductPayload = {
  name: string
  sku: string
  description?: string
  price: number
  quantity: number
  low_stock_threshold: number
}

export const getProducts = async (page = 1, pageSize = 12): Promise<ProductsResponse> => {
  const response = await client.get('/products', {
    params: { page, page_size: pageSize },
  })
  return response.data as ProductsResponse
}

export const createProduct = async (data: CreateProductPayload): Promise<Product> => {
  const response = await client.post('/products', data)
  return response.data as Product
}