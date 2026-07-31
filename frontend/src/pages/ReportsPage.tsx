import { useEffect, useState } from 'react'
import AppHeader from '../components/layout/AppHeader'
import {
  getStockSummary,
  getTopProducts,
  type StockSummaryItem,
  type TopProductItem,
} from '../api/reports'
import { getErrorMessage } from '../lib/errors'

export default function ReportsPage() {
  const [summary, setSummary] = useState<StockSummaryItem[]>([])
  const [totalValue, setTotalValue] = useState('0')
  const [topProducts, setTopProducts] = useState<TopProductItem[]>([])
  const [loading, setLoading] = useState(true)
  const [pageError, setPageError] = useState('')

  const loadReports = async () => {
    try {
      setLoading(true)
      setPageError('')

      const [summaryData, topData] = await Promise.all([
        getStockSummary(),
        getTopProducts(),
      ])

      setSummary(summaryData.items)
      setTotalValue(summaryData.total_inventory_value)
      setTopProducts(topData.items)
    } catch (err) {
      setPageError(getErrorMessage(err, 'Failed to load reports.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadReports()
  }, [])

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <AppHeader />

      <main className="space-y-8 px-8 py-8">
        <div>
          <h1 className="text-3xl font-bold">Reports</h1>
          <p className="mt-1 text-slate-400">
            Current inventory value and all-time product performance.
          </p>
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
                <h2 className="text-xl font-semibold text-white">
                  Stock summary
                </h2>
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
                        <th className="w-24 px-4 py-3 whitespace-nowrap">
                          Qty
                        </th>
                        <th className="w-28 px-4 py-3 whitespace-nowrap">
                          Price
                        </th>
                        <th className="w-32 px-4 py-3 whitespace-nowrap">
                          Value
                        </th>
                        <th className="w-28 px-4 py-3 whitespace-nowrap">
                          Status
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {summary.map((item) => (
                        <tr
                          key={item.id}
                          className="border-b border-slate-800/60 transition hover:bg-slate-800/40"
                        >
                          <td className="px-4 py-3">
                            <p className="font-semibold text-white">
                              {item.name}
                            </p>
                            <p className="text-xs text-slate-400">
                              SKU {item.sku}
                            </p>
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
                        <th className="w-28 px-4 py-3 whitespace-nowrap">
                          Units
                        </th>
                        <th className="w-28 px-4 py-3 whitespace-nowrap">
                          Orders
                        </th>
                        <th className="w-32 px-4 py-3 whitespace-nowrap">
                          Revenue
                        </th>
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
          </>
        )}
      </main>
    </div>
  )
}
