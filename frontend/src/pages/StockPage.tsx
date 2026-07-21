import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { getProduct, type Product } from '../api/products'
import {
  adjustStock,
  getStockHistory,
  type MovementType,
  type StockMovement,
} from '../api/stock'
import { Button } from '../components/ui/button'
import { getErrorMessage } from '../lib/errors'

type FormState = {
  movement_type: MovementType
  quantity: string
  note: string
}

export default function StockPage() {
  const { id } = useParams<{ id: string }>()
  const user = useAuthStore((s) => s.user)

  const [product, setProduct] = useState<Product | null>(null)
  const [movements, setMovements] = useState<StockMovement[]>([])
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [pageError, setPageError] = useState('')

  const [form, setForm] = useState<FormState>({
    movement_type: 'RECEIVE',
    quantity: '',
    note: '',
  })
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)

  const loadHistory = async (targetPage: number) => {
    if (!id) return
    const data = await getStockHistory(id, targetPage)
    setMovements(data.items)
    setTotalPages(data.total_pages)
    setPage(data.page)
  }

  const loadAll = async () => {
    if (!id) return
    try {
      setLoading(true)
      setPageError('')
      const [productData] = await Promise.all([getProduct(id), loadHistory(1)])
      setProduct(productData)
    } catch (err) {
      setPageError(getErrorMessage(err, 'Failed to load stock data.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAll()
  }, [id])

  const handlePageChange = async (nextPage: number) => {
    try {
      setPageError('')
      await loadHistory(nextPage)
    } catch (err) {
      setPageError(getErrorMessage(err, 'Failed to load stock history.'))
    }
  }

  const handleFormChange = (
    event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = event.target
    setForm((prev) => ({ ...prev, [name]: value }))
  }

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFormError('')

    if (!id) return

    const quantityNum = Number(form.quantity)

    if (!form.quantity.trim() || isNaN(quantityNum) || quantityNum === 0) {
      setFormError('Enter a non-zero quantity.')
      return
    }

    if (form.movement_type !== 'ADJUST' && quantityNum < 0) {
      setFormError('Enter a positive quantity — the sign is applied automatically.')
      return
    }

    const signedQuantity =
      form.movement_type === 'SHIP' ? -Math.abs(quantityNum) : quantityNum

    try {
      setSaving(true)
      await adjustStock(id, {
        movement_type: form.movement_type,
        quantity_change: signedQuantity,
        ...(form.note.trim() && { note: form.note.trim() }),
      })
      setForm({ movement_type: 'RECEIVE', quantity: '', note: '' })
      await loadAll()
    } catch (err) {
      setFormError(getErrorMessage(err, 'Failed to adjust stock.'))
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-white">
        <div className="px-8 py-8 text-slate-400">Loading...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800 bg-slate-900/60 px-8 py-6">
        <Link to="/dashboard" className="text-sm text-slate-400 hover:text-white">
          ← Back to dashboard
        </Link>

        {product && (
          <>
            <h1 className="mt-2 text-3xl font-bold">{product.name}</h1>
            <p className="mt-1 text-slate-400">
              SKU {product.sku} · Current quantity: {product.quantity}
            </p>
          </>
        )}
      </header>

      <main className="space-y-8 px-8 py-8">
        {pageError && (
          <div className="rounded-xl border border-red-900 bg-red-950 p-4 text-red-300">
            {pageError}
          </div>
        )}

        {user?.is_admin && (
          <form
            onSubmit={handleSubmit}
            className="rounded-xl border border-slate-800 bg-slate-900/80 p-6 shadow-lg"
          >
            <h2 className="text-xl font-semibold text-white">Adjust stock</h2>

            <div className="mt-4 grid gap-4 md:grid-cols-3">
              <div>
                <label className="mb-2 block text-sm text-slate-300">Type</label>
                <select
                  name="movement_type"
                  value={form.movement_type}
                  onChange={handleFormChange}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none transition hover:border-slate-500 focus:border-slate-500"
                >
                  <option value="RECEIVE">Receive</option>
                  <option value="SHIP">Ship</option>
                  <option value="ADJUST">Adjust</option>
                </select>
              </div>

              <div>
                <label className="mb-2 block text-sm text-slate-300">Quantity</label>
                <input
                  name="quantity"
                  type="number"
                  value={form.quantity}
                  onChange={handleFormChange}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none transition hover:border-slate-500 focus:border-slate-500"
                  placeholder="10"
                />
              </div>

              <div>
                <label className="mb-2 block text-sm text-slate-300">
                  Note <span className="text-slate-500">(optional)</span>
                </label>
                <input
                  name="note"
                  value={form.note}
                  onChange={handleFormChange}
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none transition hover:border-slate-500 focus:border-slate-500"
                  placeholder="Damaged in transit"
                />
              </div>
            </div>

            <p className="mt-2 text-xs text-slate-500">
              Receive and Ship take a positive number — the sign is applied for you.
              Adjust accepts either a positive or negative number for manual corrections.
            </p>

            {formError && (
              <div className="mt-4 rounded-lg border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-300">
                {formError}
              </div>
            )}

            <div className="mt-6">
              <Button
                type="submit"
                disabled={saving}
                className="bg-cyan-600 text-white transition hover:bg-cyan-500"
              >
                {saving ? 'Saving...' : 'Submit'}
              </Button>
            </div>
          </form>
        )}

        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-6 shadow-lg">
          <h2 className="text-xl font-semibold text-white">Movement history</h2>

          {movements.length === 0 ? (
            <p className="mt-4 text-slate-400">No movements yet.</p>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400">
                    <th className="py-2 pr-4">Date</th>
                    <th className="py-2 pr-4">Type</th>
                    <th className="py-2 pr-4">Change</th>
                    <th className="py-2 pr-4">Before → After</th>
                    <th className="py-2 pr-4">Note</th>
                  </tr>
                </thead>
                <tbody>
                  {movements.map((m) => (
                    <tr key={m.id} className="border-b border-slate-800/60">
                      <td className="py-2 pr-4 text-slate-400">
                        {new Date(m.created_at).toLocaleDateString('en-GB')}
                      </td>
                      <td className="py-2 pr-4">{m.movement_type}</td>
                      <td
                        className={`py-2 pr-4 font-semibold ${
                          m.quantity_change > 0 ? 'text-emerald-400' : 'text-red-400'
                        }`}
                      >
                        {m.quantity_change > 0 ? '+' : ''}
                        {m.quantity_change}
                      </td>
                      <td className="py-2 pr-4 text-slate-400">
                        {m.quantity_before} → {m.quantity_after}
                      </td>
                      <td className="py-2 pr-4 text-slate-400">{m.note ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {totalPages > 1 && (
            <div className="mt-4 flex items-center gap-3">
              <Button
                type="button"
                variant="outline"
                disabled={page <= 1}
                onClick={() => handlePageChange(page - 1)}
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
                onClick={() => handlePageChange(page + 1)}
              >
                Next
              </Button>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
