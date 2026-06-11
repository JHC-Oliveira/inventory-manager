import { useState } from 'react'
import { Button } from '../ui/button'
import type { CreateProductPayload } from '../../api/products'

type Props = {
  onSubmit: (data: CreateProductPayload) => Promise<void>
  onCancel: () => void
  loading: boolean
}

type FormState = {
  name: string
  sku: string
  description: string
  price: string
  quantity: string
  low_stock_threshold: string
}

export default function ProductForm({ onSubmit, onCancel, loading }: Props) {
  const [form, setForm] = useState<FormState>({
    name: '',
    sku: '',
    description: '',
    price: '',
    quantity: '',
    low_stock_threshold: '',
  })

  const [error, setError] = useState('')

  const handleChange = (
    event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = event.target

    setForm((prev) => ({
      ...prev,
      [name]: value,
    }))
  }

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')

    if (!form.name.trim()) {
      setError('Name is required.')
      return
    }

    if (!form.sku.trim()) {
      setError('SKU is required.')
      return
    }

    if (!form.price.trim()) {
      setError('Price is required.')
      return
    }

    const priceNum = parseFloat(form.price)
    const quantityNum = form.quantity.trim() === '' ? 0 : Number(form.quantity)
    const lowStockNum =
      form.low_stock_threshold.trim() === ''
        ? 10
        : Number(form.low_stock_threshold)

    if (isNaN(priceNum) || priceNum <= 0) {
      setError('Price must be a positive number.')
      return
    }

    if (isNaN(quantityNum) || quantityNum < 0) {
      setError('Quantity cannot be negative.')
      return
    }

    if (isNaN(lowStockNum) || lowStockNum < 0) {
      setError('Low stock threshold cannot be negative.')
      return
    }

    const payload: CreateProductPayload = {
      name: form.name.trim(),
      sku: form.sku.trim(),
      price: priceNum,
      quantity: quantityNum,
      low_stock_threshold: lowStockNum,
      ...(form.description.trim() && { description: form.description.trim() }),
    }

    await onSubmit(payload)
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl border border-slate-800 bg-slate-900/80 p-6 shadow-lg"
    >
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-white">Add product</h2>
        <p className="mt-1 text-sm text-slate-400">
          Create a new inventory item.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <label className="mb-2 block text-sm text-slate-300">Name</label>
          <input
            name="name"
            value={form.name}
            onChange={handleChange}
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none transition hover:border-slate-500 focus:border-slate-500"
            placeholder="Nike Air Max"
          />
        </div>

        <div>
          <label className="mb-2 block text-sm text-slate-300">SKU</label>
          <input
            name="sku"
            value={form.sku}
            onChange={handleChange}
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none transition hover:border-slate-500 focus:border-slate-500"
            placeholder="NK-AM-001"
          />
        </div>

        <div>
          <label className="mb-2 block text-sm text-slate-300">Price (€)</label>
          <input
            name="price"
            value={form.price}
            onChange={handleChange}
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none transition hover:border-slate-500 focus:border-slate-500"
            placeholder="129.99"
          />
        </div>

        <div>
          <label className="mb-2 block text-sm text-slate-300">Quantity</label>
          <input
            name="quantity"
            type="number"
            min={0}
            value={form.quantity}
            onChange={handleChange}
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none transition hover:border-slate-500 focus:border-slate-500"
            placeholder="100"
          />
        </div>

        <div>
          <label className="mb-2 block text-sm text-slate-300">
            Low stock threshold
          </label>
          <input
            name="low_stock_threshold"
            type="number"
            min={0}
            value={form.low_stock_threshold}
            onChange={handleChange}
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none transition hover:border-slate-500 focus:border-slate-500"
            placeholder="10"
          />
        </div>

        <div className="md:col-span-2">
          <label className="mb-2 block text-sm text-slate-300">
            Description <span className="text-slate-500">(optional)</span>
          </label>
          <textarea
            name="description"
            value={form.description}
            onChange={handleChange}
            rows={2}
            className="w-full resize-none rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white outline-none transition hover:border-slate-500 focus:border-slate-500"
            placeholder="Short product description..."
          />
        </div>
      </div>

      {error && (
        <div className="mt-4 rounded-lg border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="mt-6 flex gap-3">
        <Button
          type="submit"
          disabled={loading}
          className="bg-cyan-600 text-white transition hover:bg-cyan-500"
        >
          {loading ? 'Creating...' : 'Create product'}
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