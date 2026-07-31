import { Fragment, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import {
  createProduct,
  deleteProduct,
  getProducts,
  updateProduct,
  type CreateProductPayload,
  type Product,
} from '../api/products'
import AppHeader from '../components/layout/AppHeader'
import ProductCard from '../components/products/ProductCard'
import ProductForm from '../components/products/ProductForm'
import ProductsSkeleton from '../components/products/ProductsSkeleton'
import { Button } from '../components/ui/button'
import { getErrorMessage } from '../lib/errors'

export default function ProductsPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)

  const [products, setProducts] = useState<Product[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [pageError, setPageError] = useState('')
  const [formError, setFormError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create')
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [saving, setSaving] = useState(false)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)

  const loadProducts = async (targetPage: number) => {
    try {
      setLoading(true)
      setPageError('')
      const data = await getProducts(targetPage, 15)
      setProducts(data.items)
      setTotal(data.total)
      setTotalPages(data.total_pages)
      setPage(data.page)
    } catch (err) {
      setPageError(getErrorMessage(err, 'Failed to load products.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadProducts(1)
  }, [])

  const openCreateForm = () => {
    setFormMode('create')
    setSelectedProduct(null)
    setFormError('')
    setShowForm(true)
  }

  const openEditForm = (product: Product) => {
    setFormMode('edit')
    setSelectedProduct(product)
    setFormError('')
    setShowForm(true)
  }

  const handleEditClick = (product: Product) => {
    if (showForm && formMode === 'edit' && selectedProduct?.id === product.id) {
      closeForm()
    } else {
      openEditForm(product)
    }
  }

  const closeForm = () => {
    setShowForm(false)
    setSelectedProduct(null)
    setFormError('')
  }

  const handleSubmit = async (data: CreateProductPayload) => {
    try {
      setSaving(true)
      setFormError('')

      if (formMode === 'create') {
        await createProduct(data)
      } else if (selectedProduct) {
        await updateProduct(selectedProduct.id, data)
      }

      closeForm()
      await loadProducts(formMode === 'create' ? 1 : page)
    } catch (err) {
      setFormError(
        getErrorMessage(
          err,
          formMode === 'create'
            ? 'Failed to create product.'
            : 'Failed to update product.',
        ),
      )
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (product: Product) => {
    const confirmed = window.confirm(
      `Delete "${product.name}"? This action cannot be undone.`,
    )

    if (!confirmed) return

    try {
      setPageError('')
      await deleteProduct(product.id)
      await loadProducts(page)
    } catch (err) {
      setPageError(getErrorMessage(err, 'Failed to delete product.'))
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <AppHeader />

      <div className="border-b border-slate-800 bg-slate-900/40 px-8 py-4">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <p className="text-sm text-slate-400">
            {loading
              ? 'Loading...'
              : `${total} product${total !== 1 ? 's' : ''} in inventory`}
          </p>

          {user?.is_admin && (
            <Button
              onClick={() => (showForm ? closeForm() : openCreateForm())}
              className="bg-cyan-600 text-white transition hover:bg-cyan-500"
            >
              {showForm ? 'Close form' : 'Add product'}
            </Button>
          )}
        </div>
      </div>

      <main className="space-y-8 px-8 py-8">
        {user?.is_admin && showForm && formMode === 'create' && (
          <ProductForm
            mode="create"
            initialData={null}
            onSubmit={handleSubmit}
            onCancel={closeForm}
            loading={saving}
            externalError={formError}
          />
        )}

        {pageError && (
          <div className="rounded-xl border border-red-900 bg-red-950 p-4 text-red-300">
            {pageError}
          </div>
        )}

        {loading && <ProductsSkeleton />}

        {!loading && !pageError && products.length === 0 && (
          <div className="rounded-xl border border-slate-800 bg-slate-900 p-12 text-center">
            <p className="text-slate-400">No products yet.</p>
          </div>
        )}

        {!loading && products.length > 0 && (
          <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/80">
            <table className="w-full table-fixed text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="px-4 py-3">Product</th>
                  <th className="w-28 px-4 py-3 whitespace-nowrap">Quantity</th>
                  <th className="w-28 px-4 py-3 whitespace-nowrap">Price</th>
                  <th className="w-28 px-4 py-3 whitespace-nowrap">Status</th>
                  <th className="w-28 px-4 py-3 whitespace-nowrap">
                    Low stock
                  </th>
                  <th className="w-72 px-4 py-3 whitespace-nowrap">Actions</th>
                </tr>
              </thead>
              <tbody>
                {products.map((product) => {
                  const isEditing =
                    showForm &&
                    formMode === 'edit' &&
                    selectedProduct?.id === product.id

                  return (
                    <Fragment key={product.id}>
                      <ProductCard
                        name={product.name}
                        sku={product.sku}
                        description={product.description}
                        quantity={product.quantity}
                        price={product.price}
                        isLowStock={product.is_low_stock}
                        isActive={product.is_active}
                        canManage={!!user?.is_admin}
                        isEditing={isEditing}
                        onEdit={() => handleEditClick(product)}
                        onDelete={() => handleDelete(product)}
                        onManageStock={() =>
                          navigate(`/products/${product.id}/stock`)
                        }
                      />

                      {isEditing && (
                        <tr>
                          <td colSpan={6} className="bg-slate-950/60 px-4 py-4">
                            <ProductForm
                              mode="edit"
                              initialData={selectedProduct}
                              onSubmit={handleSubmit}
                              onCancel={closeForm}
                              loading={saving}
                              externalError={formError}
                            />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
            {totalPages > 1 && (
              <div className="flex items-center gap-3 border-t border-slate-800 px-4 py-4">
                <Button
                  type="button"
                  variant="outline"
                  disabled={page <= 1}
                  onClick={() => loadProducts(page - 1)}
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
                  onClick={() => loadProducts(page + 1)}
                >
                  Next
                </Button>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
