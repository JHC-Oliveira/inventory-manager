import { useState } from 'react'
import { Button } from '../ui/button'
import type { CreateOrderPayload } from '../../api/orders'
import type { Product } from '../../api/products'

type Props = {
  products: Product[]
  onSubmit: (data: CreateOrderPayload) => Promise<void>
  onCancel: () => void
  loading: boolean
  externalError?: string
}

type LineState = {
  product_id: string
  quantity: string
}

const emptyLine = (): LineState => ({ product_id: '', quantity: '1' })

export default function OrderForm({
  products,
  onSubmit,
  onCancel,
  loading,
  externalError = '',
}: Props) {
  const [customerName, setCustomerName] = useState('')
  const [lines, setLines] = useState<LineState[]>([emptyLine()])
  const [error, setError] = useState('')

  const updateLine = (index: number, field: keyof LineState, value: string) => {
    setLines((prev) =>
      prev.map((line, i) => (i === index ? { ...line, [field]: value } : line)),
    )
  }

  const addLine = () => setLines((prev) => [...prev, emptyLine()])

  const removeLine = (index: number) =>
    setLines((prev) => prev.filter((_, i) => i !== index))

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')

    if (!customerName.trim()) {
      setError('Customer name is required.')
      return
    }

    const seen = new Set<string>()
    const items = []

    for (const line of lines) {
      if (!line.product_id) {
        setError('Select a product for every line item.')
        return
      }
      if (seen.has(line.product_id)) {
        setError('Each product can only appear once — combine quantities into one line.')
        return
      }
      seen.add(line.product_id)

      const quantity = Number(line.quantity)
      if (!Number.isInteger(quantity) || quantity <= 0) {
        setError('Quantity must be a whole number greater than 0.')
        return
      }

      items.push({ product_id: line.product_id, quantity })
    }

    await onSubmit({ customer_name: customerName.trim(), items })
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl border border-slate-800 bg-slate-900/80 p-6 shadow-lg"
    >
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-white">New order</h2>
        <p className="mt-1 text-sm text-slate-400">
          Pick products and quantities — stock is checked and shipped automatically.
        </p>
      </div>

      <div>
        <label className="mb-2 block text-sm text-slate-300">Customer name</label>
        <input
          value={customerName}
          onChange={(e) => setCustomerName(e.target.value)}
          className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none transition hover:border-slate-500 focus:border-slate-500"
          placeholder="Jane Doe"
        />
      </div>

      <div className="mt-4 space-y-3">
        {lines.map((line, index) => (
          <div key={index} className="flex gap-3">
            <select
              value={line.product_id}
              onChange={(e) => updateLine(index, 'product_id', e.target.value)}
              className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none transition hover:border-slate-500 focus:border-slate-500"
            >
              <option value="">Select a product...</option>
              {products.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.sku} — {product.name} ({product.quantity} in stock)
                </option>
              ))}
            </select>

            <input
              type="number"
              min={1}
              value={line.quantity}
              onChange={(e) => updateLine(index, 'quantity', e.target.value)}
              className="w-24 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none transition hover:border-slate-500 focus:border-slate-500"
            />

            <Button
              type="button"
              variant="outline"
              onClick={() => removeLine(index)}
              disabled={lines.length === 1}
              className="transition hover:bg-slate-800 hover:text-white"
            >
              Remove
            </Button>
          </div>
        ))}
      </div>

      <Button
        type="button"
        variant="outline"
        onClick={addLine}
        className="mt-3 transition hover:bg-slate-800 hover:text-white"
      >
        + Add item
      </Button>

      {(error || externalError) && (
        <div className="mt-4 rounded-lg border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-300">
          {error || externalError}
        </div>
      )}

      <div className="mt-6 flex gap-3">
        <Button
          type="submit"
          disabled={loading}
          className="bg-cyan-600 text-white transition hover:bg-cyan-500"
        >
          {loading ? 'Placing order...' : 'Place order'}
        </Button>

        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          disabled={loading}
          className="transition hover:bg-slate-800 hover:text-white"
        >
          Cancel
        </Button>
      </div>
    </form>
  )
}
