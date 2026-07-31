import { Fragment, useEffect, useState } from 'react'
import { useAuthStore } from '../store/authStore'
import {
  cancelOrder,
  createOrder,
  getOrders,
  type CreateOrderPayload,
  type Order,
} from '../api/orders'
import { getProducts, type Product } from '../api/products'
import AppHeader from '../components/layout/AppHeader'
import OrderForm from '../components/orders/OrderForm'
import { Button } from '../components/ui/button'
import { getErrorMessage } from '../lib/errors'

const STATUS_STYLES: Record<Order['status'], string> = {
  PENDING: 'bg-amber-950 text-amber-300',
  FULFILLED: 'bg-emerald-950 text-emerald-300',
  CANCELLED: 'bg-slate-800 text-slate-400',
}

const orderTotal = (order: Order) =>
  order.items.reduce((sum, item) => sum + Number(item.subtotal), 0)

export default function OrdersPage() {
  const user = useAuthStore((s) => s.user)

  const [orders, setOrders] = useState<Order[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [pageError, setPageError] = useState('')

  const [showForm, setShowForm] = useState(false)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const [products, setProducts] = useState<Product[]>([])

  const [expandedOrderId, setExpandedOrderId] = useState<string | null>(null)

  const loadOrders = async (targetPage: number) => {
    try {
      setLoading(true)
      setPageError('')
      const data = await getOrders(targetPage, 10)
      setOrders(data.items)
      setTotal(data.total)
      setTotalPages(data.total_pages)
      setPage(data.page)
    } catch (err) {
      setPageError(getErrorMessage(err, 'Failed to load orders.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadOrders(1)
  }, [])

  const openCreateForm = async () => {
    setFormError('')
    setShowForm(true)
    try {
      const data = await getProducts(1, 100)
      setProducts(data.items)
    } catch (err) {
      setFormError(getErrorMessage(err, 'Failed to load products.'))
    }
  }

  const closeForm = () => {
    setShowForm(false)
    setFormError('')
  }

  const handleCreate = async (data: CreateOrderPayload) => {
    try {
      setSaving(true)
      setFormError('')
      await createOrder(data)
      closeForm()
      await loadOrders(1)
    } catch (err) {
      setFormError(getErrorMessage(err, 'Failed to place order.'))
    } finally {
      setSaving(false)
    }
  }

  const toggleExpand = (orderId: string) => {
    setExpandedOrderId((prev) => (prev === orderId ? null : orderId))
  }

  const handleCancel = async (order: Order) => {
    const confirmed = window.confirm(
      `Cancel order for "${order.customer_name}"? Stock will be restored.`,
    )
    if (!confirmed) return

    try {
      setPageError('')
      await cancelOrder(order.id)
      await loadOrders(page)
    } catch (err) {
      setPageError(getErrorMessage(err, 'Failed to cancel order.'))
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <AppHeader />

      <div className="border-b border-slate-800 bg-slate-900/40 px-8 py-4">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <p className="text-sm text-slate-400">
            {loading ? 'Loading...' : `${total} order${total !== 1 ? 's' : ''}`}
          </p>

          <Button
            onClick={() => (showForm ? closeForm() : openCreateForm())}
            className="bg-cyan-600 text-white transition hover:bg-cyan-500"
          >
            {showForm ? 'Close form' : 'New order'}
          </Button>
        </div>
      </div>

      <main className="space-y-8 px-8 py-8">
        {showForm && (
          <OrderForm
            products={products}
            onSubmit={handleCreate}
            onCancel={closeForm}
            loading={saving}
            externalError={formError}
          />
        )}

        {pageError && (
          <div className="rounded-xl border border-red-900 bg-red-950 p-4 text-red-300">
            {pageError}
          </div>
        )}

        {!loading && !pageError && orders.length === 0 && (
          <div className="rounded-xl border border-slate-800 bg-slate-900 p-12 text-center">
            <p className="text-slate-400">No orders yet.</p>
          </div>
        )}

        {!loading && orders.length > 0 && (
          <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/80">
            <table className="w-full table-fixed text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="px-4 py-3">Customer</th>
                  <th className="w-28 px-4 py-3 whitespace-nowrap">Status</th>
                  <th className="w-28 px-4 py-3 whitespace-nowrap">Total</th>
                  <th className="w-32 px-4 py-3 whitespace-nowrap">Date</th>
                  <th className="w-56 px-4 py-3 whitespace-nowrap">Actions</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => {
                  const isExpanded = expandedOrderId === order.id
                  const canCancel = user?.is_admin && order.status === 'PENDING'

                  return (
                    <Fragment key={order.id}>
                      <tr
                        className={`border-b border-slate-800/60 transition ${
                          isExpanded
                            ? 'bg-slate-800/60'
                            : 'hover:bg-slate-800/40'
                        }`}
                      >
                        <td className="px-4 py-3">
                          <p className="font-semibold text-white">
                            {order.customer_name}
                          </p>
                          <p className="text-xs text-slate-400">
                            {order.items.length} item
                            {order.items.length !== 1 ? 's' : ''}
                          </p>
                        </td>

                        <td className="whitespace-nowrap px-4 py-3">
                          <span
                            className={`rounded-full px-2 py-1 text-xs font-medium ${STATUS_STYLES[order.status]}`}
                          >
                            {order.status}
                          </span>
                        </td>

                        <td className="whitespace-nowrap px-4 py-3 text-slate-300">
                          €{orderTotal(order).toFixed(2)}
                        </td>

                        <td className="whitespace-nowrap px-4 py-3 text-slate-400">
                          {new Date(order.created_at).toLocaleDateString(
                            'en-GB',
                          )}
                        </td>

                        <td className="whitespace-nowrap px-4 py-3">
                          <div className="flex flex-wrap gap-2">
                            <Button
                              type="button"
                              variant="outline"
                              onClick={() => toggleExpand(order.id)}
                              className="transition hover:bg-slate-800 hover:text-white"
                            >
                              {isExpanded ? 'Hide items' : 'View items'}
                            </Button>

                            {canCancel && (
                              <Button
                                type="button"
                                variant="destructive"
                                onClick={() => handleCancel(order)}
                                className="transition hover:opacity-90"
                              >
                                Cancel
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>

                      {isExpanded && (
                        <tr>
                          <td colSpan={5} className="bg-slate-950/60 px-4 py-4">
                            <table className="w-full text-left text-sm">
                              <thead>
                                <tr className="text-slate-400">
                                  <th className="py-1 pr-4">Product</th>
                                  <th className="py-1 pr-4">SKU</th>
                                  <th className="py-1 pr-4">Qty</th>
                                  <th className="py-1 pr-4">Unit price</th>
                                  <th className="py-1 pr-4">Subtotal</th>
                                </tr>
                              </thead>
                              <tbody>
                                {order.items.map((item) => (
                                  <tr
                                    key={item.id}
                                    className="border-t border-slate-800/60"
                                  >
                                    <td className="py-2 pr-4">
                                      {item.product_name}
                                    </td>
                                    <td className="py-2 pr-4 text-slate-400">
                                      {item.product_sku}
                                    </td>
                                    <td className="py-2 pr-4">
                                      {item.quantity}
                                    </td>
                                    <td className="py-2 pr-4">
                                      €{Number(item.unit_price).toFixed(2)}
                                    </td>
                                    <td className="py-2 pr-4">
                                      €{Number(item.subtotal).toFixed(2)}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>

            {totalPages > 1 && (
              <div className="flex items-center gap-3 border-t border-slate-800 px-4 py-4">
                <Button
                  type="button"
                  variant="outline"
                  disabled={page <= 1}
                  onClick={() => loadOrders(page - 1)}
                >
                  Previous
                </Button>
                <span className="text-sm text-slate-400">
                  Page {page} of {totalPages}
                </span>
                <Button
                  type="button"
                  variant="outline"
                  disabled={page >= totalPages}
                  onClick={() => loadOrders(page + 1)}
                >
                  Next
                </Button>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
