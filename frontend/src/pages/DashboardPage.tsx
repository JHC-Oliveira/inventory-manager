import { useEffect, useState } from 'react'
import { useAuthStore } from '../store/authStore'
import { getProducts, type Product } from '../api/products'
import ProductCard from '../components/products/ProductCard'
import ProductsSkeleton from '../components/products/ProductsSkeleton'

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user)

  const [products, setProducts] = useState<Product[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        const data = await getProducts(1, 12)
        setProducts(data.items)
        setTotal(data.total)
      } catch {
        setError('Failed to load products.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/60 px-8 py-6">
        <p className="text-sm text-slate-400">Inventory Manager</p>
        <h1 className="mt-1 text-3xl font-bold">Dashboard</h1>
        <p className="mt-1 text-slate-400">
          Welcome back, {user?.full_name ?? user?.email ?? 'user'}
        </p>
      </header>

      {/* Stats bar */}
      <div className="border-b border-slate-800 bg-slate-900/40 px-8 py-4">
        <p className="text-sm text-slate-400">
          {loading ? 'Loading...' : `${total} product${total !== 1 ? 's' : ''} in inventory`}
        </p>
      </div>

      {/* Content */}
      <main className="px-8 py-8">
        {loading && <ProductsSkeleton />}

        {!loading && error && (
          <div className="rounded-xl border border-red-900 bg-red-950 p-4 text-red-300">
            {error}
          </div>
        )}

        {!loading && !error && products.length === 0 && (
          <div className="rounded-xl border border-slate-800 bg-slate-900 p-12 text-center">
            <p className="text-slate-400">No products yet.</p>
          </div>
        )}

        {!loading && !error && products.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {products.map((product) => (
              <ProductCard
                key={product.id}
                name={product.name}
                sku={product.sku}
                quantity={product.quantity}
                price={product.price}
                lowStockThreshold={product.low_stock_threshold}
                isActive={product.is_active}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}