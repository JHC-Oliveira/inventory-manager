import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppHeader from '../components/layout/AppHeader'
import {
  getLowStock,
  getMovementHistory,
  getStockSummary,
  type LowStockItem,
} from '../api/reports'
import { Button } from '../components/ui/button'
import { getErrorMessage } from '../lib/errors'

const daysAgoISO = (days: number) => {
  const date = new Date()
  date.setDate(date.getDate() - days)
  return date.toISOString().slice(0, 10)
}

export default function DashboardPage() {
  const navigate = useNavigate()

  const [totalProducts, setTotalProducts] = useState(0)
  const [inventoryValue, setInventoryValue] = useState('0')
  const [lowStockItems, setLowStockItems] = useState<LowStockItem[]>([])
  const [recentMovements, setRecentMovements] = useState(0)
  const [loading, setLoading] = useState(true)
  const [pageError, setPageError] = useState('')

  const loadDashboard = async () => {
    try {
      setLoading(true)
      setPageError('')

      const [summary, lowStock, movements] = await Promise.all([
        getStockSummary(),
        getLowStock(),
        getMovementHistory(1, 1, daysAgoISO(7)),
      ])

      setTotalProducts(summary.total_products)
      setInventoryValue(summary.total_inventory_value)
      setLowStockItems(lowStock.items)
      setRecentMovements(movements.total)
    } catch (err) {
      setPageError(getErrorMessage(err, 'Failed to load dashboard.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadDashboard()
  }, [])

  const kpis = [
    { label: 'Total products', value: totalProducts },
    {
      label: 'Inventory value',
      value: `€${Number(inventoryValue).toFixed(2)}`,
    },
    { label: 'Low stock items', value: lowStockItems.length },
    { label: 'Movements (7d)', value: recentMovements },
  ]

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <AppHeader />

      <main className="space-y-8 px-8 py-8">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="mt-1 text-slate-400">What needs attention right now.</p>
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
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {kpis.map((kpi) => (
                <div
                  key={kpi.label}
                  className="rounded-xl border border-slate-800 bg-slate-900/80 p-5"
                >
                  <p className="text-xs tracking-wide text-slate-400 uppercase">
                    {kpi.label}
                  </p>
                  <p className="mt-2 text-3xl font-bold">{kpi.value}</p>
                </div>
              ))}
            </div>

            <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-6 shadow-lg">
              <h2 className="text-xl font-semibold text-white">
                Products below threshold
              </h2>

              {lowStockItems.length === 0 ? (
                <p className="mt-4 text-slate-400">
                  Nothing is below its threshold. All good.
                </p>
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
                          Threshold
                        </th>
                        <th className="w-24 px-4 py-3 whitespace-nowrap">
                          Deficit
                        </th>
                        <th className="w-40 px-4 py-3 whitespace-nowrap">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {lowStockItems.map((item) => (
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
                          <td className="px-4 py-3 whitespace-nowrap text-slate-400">
                            {item.low_stock_threshold}
                          </td>
                          <td className="px-4 py-3 font-semibold whitespace-nowrap text-amber-300">
                            {item.quantity - item.low_stock_threshold}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <Button
                              type="button"
                              variant="outline"
                              onClick={() =>
                                navigate(`/products/${item.id}/stock`)
                              }
                              className="transition hover:bg-slate-800 hover:text-white"
                            >
                              Manage stock
                            </Button>
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
