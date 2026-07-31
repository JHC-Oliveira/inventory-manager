import client from './client'

export type Product = {
  id: string
  name: string
  description: string | null
  sku: string
  price: string
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
  total_pages: number
}

export type CreateProductPayload = {
  name: string
  sku: string
  description?: string
  price: number
  quantity: number
  low_stock_threshold: number
}

export type UpdateProductPayload = {
  name?: string
  description?: string
  price?: number
  quantity?: number
  low_stock_threshold?: number
  is_active?: boolean
}

export const getProducts = async (
  page = 1,
  pageSize = 12,
): Promise<ProductsResponse> => {
  const response = await client.get('/products', {
    params: { page, page_size: pageSize },
  })
  return response.data as ProductsResponse
}

export const getProduct = async (productId: string): Promise<Product> => {
  const response = await client.get(`/products/${productId}`)
  return response.data as Product
}

export const createProduct = async (
  data: CreateProductPayload,
): Promise<Product> => {
  const response = await client.post('/products', data)
  return response.data as Product
}

export const updateProduct = async (
  productId: string,
  data: UpdateProductPayload,
): Promise<Product> => {
  const response = await client.put(`/products/${productId}`, data)
  return response.data as Product
}

export const deleteProduct = async (productId: string): Promise<void> => {
  await client.delete(`/products/${productId}`)
}
