type Props = {
  name: string
  sku: string
  quantity: number
  price: string
  lowStockThreshold: number
  isActive: boolean
}

export default function ProductCard({
  name, sku, quantity, price, lowStockThreshold, isActive,
}: Props) {
  const lowStock = quantity <= lowStockThreshold

  return (
    <article className="rounded-xl border border-slate-800 bg-slate-900 p-4 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-white">{name}</h3>
          <p className="mt-1 text-sm text-slate-400">SKU {sku}</p>
        </div>
        <span className={`rounded-full px-2 py-1 text-xs font-medium ${
          isActive
            ? 'bg-emerald-950 text-emerald-300'
            : 'bg-slate-800 text-slate-400'
        }`}>
          {isActive ? 'Active' : 'Inactive'}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-lg bg-slate-800 p-3">
          <p className="text-slate-400">Quantity</p>
          <p className="mt-1 font-semibold text-white">{quantity}</p>
        </div>
        <div className="rounded-lg bg-slate-800 p-3">
          <p className="text-slate-400">Price</p>
          <p className="mt-1 font-semibold text-white">€{price}</p>
        </div>
      </div>

      {lowStock && (
        <p className="mt-4 rounded-lg bg-amber-950 px-3 py-2 text-sm text-amber-300">
          ⚠ Low stock — reorder soon
        </p>
      )}
    </article>
  )
}