import { useEffect, useState } from 'react'
import { useAuthStore } from '../store/authStore'
import {
  createProduct,
  getProducts,
  type CreateProductPayload,
  type Product,
} from '../api/products'
import ProductCard from '../components/products/ProductCard'
import ProductForm from '../components/products/ProductForm'
import ProductsSkeleton from '../components/products/ProductsSkeleton'
import { Button } from '../components/ui/button'

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user)

  const [products, setProducts] = useState<Product[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [creating, setCreating] = useState(false)

  const loadProducts = async () => {
    try {
      setLoading(true)
      setError('')
      const data = await getProducts(1, 12)
      setProducts(data.items)
      setTotal(data.total)
    } catch {
      setError('Failed to load products.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadProducts()
  }, [])

  const handleCreateProduct = async (data: CreateProductPayload) => {
    try {
      setCreating(true)
      await createProduct(data)
      setShowForm(false)
      await loadProducts()
    } catch {
      setError('Failed to create product.')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800 bg-slate-900/60 px-8 py-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm text-slate-400">Inventory Manager</p>
            <h1 className="mt-1 text-3xl font-bold">Dashboard</h1>
            <p className="mt-1 text-slate-400">
              Welcome back, {user?.full_name ?? user?.email ?? 'user'}
            </p>
          </div>

          {user?.is_admin && (
            <Button
              onClick={() => setShowForm((prev) => !prev)}
              className="bg-cyan-600 text-white transition hover:bg-cyan-500"
            >
              {showForm ? 'Close form' : 'Add product'}
            </Button>
          )}
        </div>
      </header>

      <div className="border-b border-slate-800 bg-slate-900/40 px-8 py-4">
        <p className="text-sm text-slate-400">
          {loading ? 'Loading...' : `${total} product${total !== 1 ? 's' : ''} in inventory`}
        </p>
      </div>

      <main className="space-y-8 px-8 py-8">
        {user?.is_admin && showForm && (
          <ProductForm
            onSubmit={handleCreateProduct}
            onCancel={() => setShowForm(false)}
            loading={creating}
          />
        )}

        {error && (
          <div className="rounded-xl border border-red-900 bg-red-950 p-4 text-red-300">
            {error}
          </div>
        )}

        {loading && <ProductsSkeleton />}

        {!loading && !error && products.length === 0 && (
          <div className="rounded-xl border border-slate-800 bg-slate-900 p-12 text-center">
            <p className="text-slate-400">No products yet.</p>
          </div>
        )}

        {!loading && products.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {products.map((product) => (
              <ProductCard
                key={product.id}
                name={product.name}
                sku={product.sku}
                description={product.description}
                quantity={product.quantity}
                price={product.price}
                isLowStock={product.is_low_stock}   
                isActive={product.is_active}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}