import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import AppHeader from '../components/layout/AppHeader'
import {
  getAllMovements,
  type MovementType,
  type StockMovement,
} from '../api/stock'
import { Button } from '../components/ui/button'
import { getErrorMessage } from '../lib/errors'

const FILTERS: { label: string; value: MovementType | 'ALL' }[] = [
  { label: 'All', value: 'ALL' },
  { label: 'Receive', value: 'RECEIVE' },
  { label: 'Ship', value: 'SHIP' },
  { label: 'Adjust', value: 'ADJUST' },
]

export default function MovementsPage() {
  const [movements, setMovements] = useState<StockMovement[]>([])
  const [filter, setFilter] = useState<MovementType | 'ALL'>('ALL')
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [loading, setLoading] = useState(true)
  const [pageError, setPageError] = useState('')

  const loadMovements = async (
    targetPage: number,
    targetFilter: MovementType | 'ALL',
  ) => {
    try {
      setLoading(true)
      setPageError('')
      const data = await getAllMovements(
        targetPage,
        20,
        targetFilter === 'ALL' ? undefined : targetFilter,
      )
      setMovements(data.items)
      setTotalPages(data.total_pages)
      setPage(data.page)
    } catch (err) {
      setPageError(getErrorMessage(err, 'Failed to load movements.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadMovements(1, filter)
  }, [filter])

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <AppHeader />

      <main className="space-y-6 px-8 py-8">
        <div>
          <h1 className="text-3xl font-bold">Movements</h1>
          <p className="mt-1 text-slate-400">
            Full stock movement history across all products.
          </p>
        </div>

        <div className="flex gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              onClick={() => setFilter(f.value)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                filter === f.value
                  ? 'bg-cyan-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {pageError && (
          <div className="rounded-xl border border-red-900 bg-red-950 p-4 text-red-300">
            {pageError}
          </div>
        )}

        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-6 shadow-lg">
          {loading ? (
            <p className="text-slate-400">Loading...</p>
          ) : movements.length === 0 ? (
            <p className="text-slate-400">No movements found.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400">
                    <th className="py-2 pr-4">Date</th>
                    <th className="py-2 pr-4">Product</th>
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
                      <td className="py-2 pr-4">
                        {m.product_id ? (
                          <Link
                            to={`/products/${m.product_id}/stock`}
                            className="text-cyan-400 hover:underline"
                          >
                            {m.product_sku}
                          </Link>
                        ) : (
                          <span className="text-slate-500">
                            {m.product_sku} (deleted)
                          </span>
                        )}
                      </td>
                      <td className="py-2 pr-4">{m.movement_type}</td>
                      <td
                        className={`py-2 pr-4 font-semibold ${
                          m.quantity_change > 0
                            ? 'text-emerald-400'
                            : 'text-red-400'
                        }`}
                      >
                        {m.quantity_change > 0 ? '+' : ''}
                        {m.quantity_change}
                      </td>
                      <td className="py-2 pr-4 text-slate-400">
                        {m.quantity_before} → {m.quantity_after}
                      </td>
                      <td
                        className="max-w-[200px] truncate py-2 pr-4 text-slate-400"
                        title={m.note ?? undefined}
                      >
                        {m.note ?? '—'}
                      </td>
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
                onClick={() => loadMovements(page - 1, filter)}
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
                onClick={() => loadMovements(page + 1, filter)}
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
