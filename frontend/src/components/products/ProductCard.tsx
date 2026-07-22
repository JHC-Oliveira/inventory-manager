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
  isEditing?: boolean
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
  isEditing = false,
  onEdit,
  onDelete,
  onManageStock,
}: Props) {
  return (
    <tr
      className={`border-b border-slate-800/60 transition ${
        isEditing ? 'bg-slate-800/60' : 'hover:bg-slate-800/40'
      }`}
    >
      <td className="px-4 py-3">
        <p className="font-semibold text-white">{name}</p>
        <p className="text-xs text-slate-400">SKU {sku}</p>
        {description && (
          <p
            className="mt-0.5 max-w-[240px] truncate text-xs text-slate-500"
            title={description}
          >
            {description}
          </p>
        )}
      </td>

      <td className="whitespace-nowrap px-4 py-3 text-slate-300">{quantity}</td>

      <td className="whitespace-nowrap px-4 py-3 text-slate-300">€{Number(price).toFixed(2)}</td>

      <td className="whitespace-nowrap px-4 py-3">
        <span
          className={`rounded-full px-2 py-1 text-xs font-medium ${
            isActive
              ? 'bg-emerald-950 text-emerald-300'
              : 'bg-slate-800 text-slate-400'
          }`}
        >
          {isActive ? 'Active' : 'Inactive'}
        </span>
      </td>

      <td className="whitespace-nowrap px-4 py-3">
        {isLowStock && (
          <span className="rounded-full bg-amber-950 px-2 py-1 text-xs font-medium text-amber-300">
            Low stock
          </span>
        )}
      </td>

      <td className="whitespace-nowrap px-4 py-3">
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={onManageStock}
            className="transition hover:bg-slate-800 hover:text-white"
          >
            Manage stock
          </Button>

          {canManage && (
            <>
              <Button
                type="button"
                variant="outline"
                onClick={onEdit}
                className="transition hover:bg-slate-800 hover:text-white"
              >
                {isEditing ? 'Cancel' : 'Edit'}
              </Button>

              <Button
                type="button"
                variant="destructive"
                onClick={onDelete}
                className="transition hover:opacity-90"
              >
                Delete
              </Button>
            </>
          )}
        </div>
      </td>
    </tr>
  )
}
