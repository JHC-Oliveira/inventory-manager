import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import AppHeader from '../components/layout/AppHeader'
import {
  getMovementHistory,
  getStockSummary,
  getTopProducts,
  type MovementHistoryItem,
  type StockSummaryItem,
  type TopProductItem,
} from '../api/reports'
import { Button } from '../components/ui/button'
import { getErrorMessage } from '../lib/errors'

export default function ReportsPage() {
  const [summary, setSummary] = useState<StockSummaryItem[]>([])
  const [totalValue, setTotalValue] = useState('0')
  const [topProducts, setTopProducts] = useState<TopProductItem[]>([])

  const [movements, setMovements] = useState<MovementHistoryItem[]>([])
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)

  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [appliedRange, setAppliedRange] = useState({ start: '', end: '' })

  const [loading, setLoading] = useState(true)
  const [pageError, setPageError] = useState('')

  const loadReports = async (
    targetPage: number,
    range: { start: string; end: string },
  ) => {
    try {
      setLoading(true)
      setPageError('')

      const [summaryData, topData, movementData] = await Promise.all([
        getStockSummary(),
        getTopProducts(),
        getMovementHistory(
          targetPage,
          10,
          range.start || undefined,
          range.end || undefined,
        ),
      ])

      setSummary(summaryData.items)
      setTotalValue(summaryData.total_inventory_value)
      setTopProducts(topData.items)
      setMovements(movementData.items)
      setTotalPages(movementData.total_pages)
      setPage(movementData.page)
    } catch (err) {
      setPageError(getErrorMessage(err, 'Failed to load reports.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadReports(1, appliedRange)
  }, [appliedRange])

  const applyRange = () => {
    if (startDate && endDate && startDate > endDate) {
      setPageError('Start date must be before end date.')
      return
    }
    setAppliedRange({ start: startDate, end: endDate })
  }

  const clearRange = () => {
    setStartDate('')
    setEndDate('')
    setAppliedRange({ start: '', end: '' })
  }

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <AppHeader />

      <main className="space-y-8 px-8 py-8">
        <div>
          <h1 className="text-3xl font-bold">Reports</h1>
          <p className="mt-1 text-slate-400">
            Inventory analysis and movement history over a period.
          </p>
        </div>

        <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-800 bg-slate-900/80 p-6">
          <div>
            <label className="mb-2 block text-sm text-slate-300">Start date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none transition hover:border-slate-500 focus:border-slate-500"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm text-slate-300">End date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none transition hover:border-slate-500 focus:border-slate-500"
            />
          </div>

          <Button
            type="button"
            onClick={applyRange}
            className="bg-cyan-600 text-white transition hover:bg-cyan-500"
          >
            Apply
          </Button>

          {(appliedRange.start || appliedRange.end) && (
            <Button
              type="button"
              variant="outline"
              onClick={clearRange}
              className="transition hover:bg-slate-800 hover:text-white"
            >
              Clear
            </Button>
          )}
        </div>

        {pageError && (
          <div className="rounded-xl border border-red-900 bg-red-950 p-4 text-red-300">
            {pageError}
          </div>
        )}

        {loading ? (
          <p className="text-slate-400">Loading...</p>
        ) : (
          <>
            <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-6 shadow-lg">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-xl font-semibold text-white">Stock summary</h2>
                <p className="text-sm text-slate-400">
                  Total inventory value:{' '}
                  <span className="font-semibold text-white">
                    €{Number(totalValue).toFixed(2)}
                  </span>
                </p>
              </div>

              {summary.length === 0 ? (
                <p className="mt-4 text-slate-400">No active products.</p>
              ) : (
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full table-fixed text-left text-sm">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400">
                        <th className="px-4 py-3">Product</th>
                        <th className="w-24 px-4 py-3 whitespace-nowrap">Qty</th>
                        <th className="w-28 px-4 py-3 whitespace-nowrap">Price</th>
                        <th className="w-32 px-4 py-3 whitespace-nowrap">Value</th>
                        <th className="w-28 px-4 py-3 whitespace-nowrap">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {summary.map((item) => (
                        <tr
                          key={item.id}
                          className="border-b border-slate-800/60 transition hover:bg-slate-800/40"
                        >
                          <td className="px-4 py-3">
                            <p className="font-semibold text-white">{item.name}</p>
                            <p className="text-xs text-slate-400">SKU {item.sku}</p>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-slate-300">
                            {item.quantity}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-slate-300">
                            €{Number(item.price).toFixed(2)}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-slate-300">
                            €{Number(item.inventory_value).toFixed(2)}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            {item.is_low_stock && (
                              <span className="rounded-full bg-amber-950 px-2 py-1 text-xs font-medium text-amber-300">
                                Low stock
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-6 shadow-lg">
              <h2 className="text-xl font-semibold text-white">Top products</h2>
              <p className="mt-1 text-xs text-slate-500">
                Aggregated across all orders, including cancelled ones.
              </p>

              {topProducts.length === 0 ? (
                <p className="mt-4 text-slate-400">No orders yet.</p>
              ) : (
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full table-fixed text-left text-sm">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400">
                        <th className="px-4 py-3">Product</th>
                        <th className="w-28 px-4 py-3 whitespace-nowrap">Units</th>
                        <th className="w-28 px-4 py-3 whitespace-nowrap">Orders</th>
                        <th className="w-32 px-4 py-3 whitespace-nowrap">Revenue</th>
                      </tr>
                    </thead>
                    <tbody>
                      {topProducts.map((item) => (
                        <tr
                          key={item.product_sku}
                          className="border-b border-slate-800/60 transition hover:bg-slate-800/40"
                        >
                          <td className="px-4 py-3">
                            <p className="font-semibold text-white">
                              {item.product_name}
                            </p>
                            <p className="text-xs text-slate-400">
                              SKU {item.product_sku}
                            </p>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-slate-300">
                            {item.total_quantity}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-slate-400">
                            {item.total_orders}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-slate-300">
                            €{Number(item.total_revenue).toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-6 shadow-lg">
              <h2 className="text-xl font-semibold text-white">Movement history</h2>

              {movements.length === 0 ? (
                <p className="mt-4 text-slate-400">
                  No movements in the selected period.
                </p>
              ) : (
                <div className="mt-4 overflow-x-auto">
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
                    onClick={() => loadReports(page - 1, appliedRange)}
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
                    onClick={() => loadReports(page + 1, appliedRange)}
                  >
                    Next
                  </Button>
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  )
}
