import { Button } from '../ui/button'

type Props = {
  name: string
  sku: string
  description: string | null
  quantity: number
  price: string | number
  isLowStock: boolean
  isActive: boolean
  canManage?: boolean
  onEdit?: () => void
  onDelete?: () => void
  onManageStock?: () => void
}

export default function ProductCard({
  name,
  sku,
  description,
  quantity,
  price,
  isLowStock,
  isActive,
  canManage = false,
  onEdit,
  onDelete,
  onManageStock,
}: Props) {
  return (
    <article className="rounded-xl border border-slate-800 bg-slate-900 p-4 shadow-sm transition hover:border-slate-700 hover:bg-slate-800/80">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-white">{name}</h3>
          <p className="mt-1 text-sm text-slate-400">SKU {sku}</p>

          {description && (
            <p className="mt-2 text-sm text-slate-500">{description}</p>
          )}
        </div>

        <span
          className={`rounded-full px-2 py-1 text-xs font-medium ${isActive
              ? 'bg-emerald-950 text-emerald-300'
              : 'bg-slate-800 text-slate-400'
            }`}
        >
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
          <p className="mt-1 font-semibold text-white">
            €{Number(price).toFixed(2)}
          </p>
        </div>
      </div>

      {isLowStock && (
        <p className="mt-4 rounded-lg bg-amber-950 px-3 py-2 text-sm text-amber-300">
          Low stock — reorder soon
        </p>
      )}

      <div className="mt-4">
        <Button
          type="button"
          variant="outline"
          onClick={onManageStock}
          className="w-full transition hover:bg-slate-800 hover:text-white"
        >
          Manage stock
        </Button>
      </div>


      {canManage && (
        <div className="mt-4 flex gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={onEdit}
            className="transition hover:bg-slate-800 hover:text-white"
          >
            Edit
          </Button>

          <Button
            type="button"
            variant="destructive"
            onClick={onDelete}
            className="transition hover:opacity-90"
          >
            Delete
          </Button>
        </div>
      )}
    </article>
  )
}