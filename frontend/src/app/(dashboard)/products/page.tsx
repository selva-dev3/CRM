'use client';

import { Input } from "@/components/ui/input";

import { ResponsiveSelect } from '@/components/common/responsive-select';

import { ActionMenu } from '@/components/common/action-menu';
import { Button } from '@/components/ui/button';
import { getErrorMessage } from '@/lib/utils';
import React, { useState, useEffect } from 'react';
import {
  Package,
  Tag,
  DollarSign,
  Layers,
  Plus,
  Download,
  Upload,
  Trash2,
  Edit,
  BookOpen,
  Boxes,
  CheckCircle2,
  AlertCircle,
  X,
  Loader2,
} from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { ModalShell } from '@/components/common/modal-shell';
import { PermissionGate } from '@/components/common/permission-gate';
import { PERMISSIONS } from '@/lib/permissions';
import {
  useProductsQuery,
  useProductCategoriesQuery,
  usePriceBooksQuery,
  useTaxRatesQuery,
  useCreateProductMutation,
  useUpdateProductMutation,
  useDeleteProductMutation,
  useBulkDeleteProductsMutation,
  useCreateCategoryMutation,
  useCreatePriceBookMutation,
  useImportProductsCsvMutation,
  useUpdateProductInventoryMutation,
  exportProductsCsvApi,
  ProductItem,
  ProductCreatePayload
} from '@/lib/api/products';

export default function ProductsPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [page, setPage] = useState(1);
  const limit = 15;

  // Selected products for bulk action
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Modal states
  const [isProductModalOpen, setIsProductModalOpen] = useState(false);
  const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
  const [isPriceBookModalOpen, setIsPriceBookModalOpen] = useState(false);
  const [inventoryProduct, setInventoryProduct] = useState<ProductItem | null>(null);
  const [editingProduct, setEditingProduct] = useState<ProductItem | null>(null);
  const [productToDelete, setProductToDelete] = useState<ProductItem | null>(null);

  // Form states
  const [prodName, setProdName] = useState('');
  const [prodSku, setProdSku] = useState('');
  const [prodPrice, setProdPrice] = useState('1000');
  const [prodCategory, setProdCategory] = useState('Software');

  // Category form state
  const [newCatName, setNewCatName] = useState('');

  // Price Book form state
  const [pbName, setPbName] = useState('');
  const [pbCurrency, setPbCurrency] = useState('USD');

  // Inventory form state
  const [quantityDelta, setQuantityDelta] = useState('25');

  // Toast / Alert notifications
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Debounce search
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
      setPage(1);
    }, 250);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  // Queries
  const { data: products = [], isLoading: isProductsLoading } = useProductsQuery({
    page,
    limit,
    category: categoryFilter || undefined,
    search: debouncedSearchTerm || undefined,
  });

  const { data: categories = [] } = useProductCategoriesQuery();
  usePriceBooksQuery();
  useTaxRatesQuery();

  // Mutations
  const createProductMutation = useCreateProductMutation();
  const updateProductMutation = useUpdateProductMutation();
  const deleteProductMutation = useDeleteProductMutation();
  const bulkDeleteMutation = useBulkDeleteProductsMutation();
  const createCategoryMutation = useCreateCategoryMutation();
  const createPriceBookMutation = useCreatePriceBookMutation();
  const importCsvMutation = useImportProductsCsvMutation();
  const updateInventoryMutation = useUpdateProductInventoryMutation();

  const resetProductForm = () => {
    setProdName('');
    setProdSku('');
    setProdPrice('1000');
    setProdCategory('Software');
    setEditingProduct(null);
  };

  const handleOpenCreateModal = () => {
    resetProductForm();
    setIsProductModalOpen(true);
  };

  const handleOpenEditModal = (p: ProductItem) => {
    setEditingProduct(p);
    setProdName(p.name);
    setProdSku(p.sku);
    setProdPrice(String(p.price));
    setProdCategory(p.category || 'Software');
    setIsProductModalOpen(true);
  };

  const handleSaveProductSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prodName.trim()) {
      setErrorMessage('Product name is required.');
      return;
    }

    const payload: ProductCreatePayload = {
      name: prodName.trim(),
      sku: prodSku.trim() || `SKU-${prodName.trim().substring(0, 4).toUpperCase()}`,
      price: parseFloat(prodPrice || '0'),
      category: prodCategory,
    };

    try {
      if (editingProduct) {
        await updateProductMutation.mutateAsync({ id: editingProduct.id, payload });
        setSuccessMessage(`Product "${prodName}" updated successfully.`);
      } else {
        await createProductMutation.mutateAsync(payload);
        setSuccessMessage(`Product "${prodName}" added to catalog.`);
      }
      setIsProductModalOpen(false);
      resetProductForm();
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to save product.'));
    }
  };

  const handleCreateCategorySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCatName.trim()) return;
    try {
      await createCategoryMutation.mutateAsync(newCatName.trim());
      setSuccessMessage(`Category tier "${newCatName.trim()}" created.`);
      setIsCategoryModalOpen(false);
      setNewCatName('');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to create category.'));
    }
  };

  const handleCreatePriceBookSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pbName.trim()) return;
    try {
      await createPriceBookMutation.mutateAsync({ name: pbName.trim(), currency: pbCurrency });
      setSuccessMessage(`Price book "${pbName.trim()}" (${pbCurrency}) created.`);
      setIsPriceBookModalOpen(false);
      setPbName('');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to create price book.'));
    }
  };

  const handleExportCsv = async () => {
    try {
      const res = await exportProductsCsvApi();
      setSuccessMessage(`Catalog exported. Download URL generated.`);
      window.open(res.download_url, '_blank');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to export CSV catalog.'));
    }
  };

  const handleImportCsv = async () => {
    try {
      const res = await importCsvMutation.mutateAsync();
      setSuccessMessage(res.message || 'CSV catalog import processing completed.');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to import CSV catalog.'));
    }
  };

  const handleUpdateInventorySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inventoryProduct) return;
    const delta = parseInt(quantityDelta || '0', 10);
    try {
      await updateInventoryMutation.mutateAsync({ id: inventoryProduct.id, delta });
      setSuccessMessage(`Stock level updated by ${delta} for ${inventoryProduct.name}.`);
      setInventoryProduct(null);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to update stock level.'));
    }
  };

  const handleDeleteProduct = async () => {
    if (!productToDelete) return;
    try {
      await deleteProductMutation.mutateAsync(productToDelete.id);
      setSuccessMessage('Product deleted from catalog.');
      setProductToDelete(null);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to delete product.'));
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    try {
      const res = await bulkDeleteMutation.mutateAsync(Array.from(selectedIds));
      setSuccessMessage(`${res.affected_count || selectedIds.size} product(s) deleted.`);
      setSelectedIds(new Set());
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to delete selected products.'));
    }
  };

  // Columns definition
  const columns: DataTableColumn<ProductItem>[] = [
    {
      id: 'name',
      header: 'PRODUCT NAME & SKU',
      cell: (item) => (
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600 font-bold shrink-0">
            <Package className="w-4 h-4" />
          </div>
          <div>
            <div className="font-bold text-slate-900 text-xs">{item.name}</div>
            <div className="text-[11px] text-slate-400 font-mono flex items-center gap-1">
              <Tag className="w-3 h-3 text-slate-400" />
              {item.sku}
            </div>
          </div>
        </div>
      ),
    },
    {
      id: 'category',
      header: 'CATEGORY TIER',
      cell: (item) => (
        <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
          {item.category || 'Software'}
        </span>
      ),
    },
    {
      id: 'price',
      header: 'LIST PRICE (USD)',
      cell: (item) => (
        <div className="flex items-center gap-1 text-emerald-600 font-bold text-xs">
          <DollarSign className="w-3.5 h-3.5 text-emerald-500" />
          <span>{item.price ? item.price.toLocaleString(undefined, { minimumFractionDigits: 2 }) : '0.00'}</span>
        </div>
      ),
    },
    {
      id: 'in_stock_quantity',
      header: 'STOCK LEVEL',
      cell: (item) => (
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-slate-800">{item.in_stock_quantity ?? 100} Units</span>
          <button
            onClick={() => setInventoryProduct(item)}
            title="Adjust Stock Quantity"
            className="p-1 text-xs text-indigo-600 hover:bg-indigo-50 rounded transition-colors font-semibold"
          >
            Adjust
          </button>
        </div>
      ),
    },
    {
      id: 'actions',
      header: 'ACTIONS',
      cell: (item) => (
        <ActionMenu
          iconOnly
          label="Open product actions"
          onTriggerClick={(event) => event.stopPropagation()}
          actions={[
            { label: 'Edit product', permission: PERMISSIONS.PRODUCTS.UPDATE, icon: <Edit className="w-4 h-4 text-indigo-600" />, onSelect: () => handleOpenEditModal(item) },
            { label: 'Delete product', permission: PERMISSIONS.PRODUCTS.DELETE, icon: <Trash2 className="w-4 h-4" />, variant: 'destructive', onSelect: () => setProductToDelete(item) },
          ]}
        />
      ),
    },
  ];

  return (
    <div className="space-y-6 w-full pb-12">
      {/* Toast Feedback */}
      {successMessage && (
        <div className="flex items-center justify-between p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl shadow-sm">
          <div className="flex items-center gap-2 text-sm font-medium">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            <span className="truncate max-w-2xl">{successMessage}</span>
          </div>
          <button type="button" aria-label="Dismiss success message" onClick={() => setSuccessMessage(null)} className="text-emerald-600 hover:text-emerald-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {errorMessage && (
        <div className="flex items-center justify-between p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl shadow-sm">
          <div className="flex items-center gap-2 text-sm font-medium">
            <AlertCircle className="w-5 h-5 text-rose-600" />
            <span>{errorMessage}</span>
          </div>
          <button type="button" aria-label="Dismiss error message" onClick={() => setErrorMessage(null)} className="text-rose-600 hover:text-rose-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Package className="w-7 h-7 text-indigo-600" />
            Product Catalog & Pricing
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">Manage products, custom price books, category tiers, inventory stock & CSV imports</p>
        </div>

        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <PermissionGate permission={PERMISSIONS.PRODUCTS.CREATE}>
            <Button onClick={handleOpenCreateModal} className="w-full gap-2 text-xs font-semibold sm:w-auto">
              <Plus className="w-4 h-4" />Add Product
            </Button>
          </PermissionGate>
          <ActionMenu label="More" className="w-full text-xs font-semibold sm:w-auto" actions={[
            { label: 'Export CSV', permission: PERMISSIONS.PRODUCTS.EXPORT, icon: <Download className="w-4 h-4 text-slate-600" />, onSelect: handleExportCsv },
            { label: 'Import CSV', permission: PERMISSIONS.PRODUCTS.IMPORT, icon: importCsvMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4 text-indigo-600" />, disabled: importCsvMutation.isPending, onSelect: handleImportCsv },
            { label: 'Add category', permission: PERMISSIONS.PRODUCTS.CREATE, icon: <Layers className="w-4 h-4 text-purple-600" />, onSelect: () => setIsCategoryModalOpen(true) },
            { label: 'Price book', icon: <BookOpen className="w-4 h-4 text-amber-500" />, onSelect: () => setIsPriceBookModalOpen(true) },
          ]} />
        </div>
      </div>



      {/* Main Data Table */}
      <DataTable<ProductItem>
        columns={columns}
        data={products}
        getRowKey={(item) => item.id}
        emptyTitle="No products found"
        emptyDescription="Add new products to catalog or import via CSV."
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search product name or SKU..."
        toolbarActions={
          <div className="flex items-center gap-3">
            <ResponsiveSelect
              value={categoryFilter}
              onValueChange={setCategoryFilter}
              className="bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-700 outline-none shadow-xs"
            >
              <option value="">All Categories</option>
              {categories.map((cat, idx) => (
                <option key={idx} value={cat}>
                  {cat}
                </option>
              ))}
            </ResponsiveSelect>

            {selectedIds.size > 0 && (
              <div className="flex w-full flex-wrap items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1 sm:w-auto">
                <span className="text-xs font-semibold text-indigo-700">{selectedIds.size} selected</span>
                <PermissionGate permission={PERMISSIONS.PRODUCTS.DELETE}>
                  <button
                    onClick={handleBulkDelete}
                    className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded text-xs font-semibold cursor-pointer"
                  >
                    Bulk Delete
                  </button>
                </PermissionGate>
              </div>
            )}
          </div>
        }
        isLoading={isProductsLoading}
        pagination={{
          pageIndex: page - 1,
          pageCount: products.length >= limit ? page + 1 : page,
          onPageChange: (p) => setPage(p + 1),
          totalRecords: (page - 1) * limit + products.length,
        }}
      />

      {/* Create / Edit Product Modal */}
      <ModalShell
        isOpen={isProductModalOpen}
        onClose={() => setIsProductModalOpen(false)}
        size="lg"
        title={
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Package className="w-5 h-5 text-indigo-600" />
            {editingProduct ? 'Edit Catalog Product' : 'Add New Catalog Product'}
          </h2>
        }
      >
        <form onSubmit={handleSaveProductSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
              Product Name *
            </label>
            <Input
              type="text"
              required
              value={prodName}
              onChange={(e) => setProdName(e.target.value)}
              placeholder="e.g. Enterprise CRM Annual Subscription"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                SKU Identifier
              </label>
              <Input
                type="text"
                value={prodSku}
                onChange={(e) => setProdSku(e.target.value)}
                placeholder="e.g. SKU-CRM-ENT"
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                Price (USD) *
              </label>
              <Input
                type="number"
                step="0.01"
                required
                value={prodPrice}
                onChange={(e) => setProdPrice(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
              Category Tier
            </label>
            <ResponsiveSelect
              value={prodCategory}
              onValueChange={setProdCategory}
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
            >
              <option value="Software">Software</option>
              <option value="Hardware">Hardware</option>
              <option value="Professional Services">Professional Services</option>
              <option value="Subscription">Subscription</option>
              <option value="Support Tier">Support Tier</option>
            </ResponsiveSelect>
          </div>

          <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-3 border-t border-slate-100">
            <button type="button" onClick={() => setIsProductModalOpen(false)} className="px-4 py-2 text-sm font-medium text-slate-600">
              Cancel
            </button>
            <button
              type="submit"
              disabled={createProductMutation.isPending || updateProductMutation.isPending}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-lg font-medium text-sm cursor-pointer shadow-sm disabled:opacity-50"
            >
              {(createProductMutation.isPending || updateProductMutation.isPending) && (
                <Loader2 className="w-4 h-4 animate-spin" />
              )}
              {editingProduct ? 'Save Changes' : 'Create Product'}
            </button>
          </div>
        </form>
      </ModalShell>

      {/* Create Category Modal */}
      <ModalShell
        isOpen={isCategoryModalOpen}
        onClose={() => setIsCategoryModalOpen(false)}
        size="md"
        title={
          <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Layers className="w-5 h-5 text-purple-600" />
            Add Product Category
          </h3>
        }
      >
        <form onSubmit={handleCreateCategorySubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Category Name *</label>
            <Input
              type="text"
              required
              value={newCatName}
              onChange={(e) => setNewCatName(e.target.value)}
              placeholder="e.g. AI Addons"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
            <button type="button" onClick={() => setIsCategoryModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
              Cancel
            </button>
            <button
              type="submit"
              disabled={createCategoryMutation.isPending}
              className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
            >
              {createCategoryMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Save Category
            </button>
          </div>
        </form>
      </ModalShell>

      {/* Create Price Book Modal */}
      <ModalShell
        isOpen={isPriceBookModalOpen}
        onClose={() => setIsPriceBookModalOpen(false)}
        size="md"
        title={
          <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-amber-500" />
            Create Price Book
          </h3>
        }
      >
        <form onSubmit={handleCreatePriceBookSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Price Book Name *</label>
            <Input
              type="text"
              required
              value={pbName}
              onChange={(e) => setPbName(e.target.value)}
              placeholder="e.g. EMEA Enterprise Book"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-amber-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Currency Code</label>
            <ResponsiveSelect
              value={pbCurrency}
              onValueChange={setPbCurrency}
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-amber-500"
            >
              <option value="USD">USD ($)</option>
              <option value="EUR">EUR (â‚¬)</option>
              <option value="GBP">GBP (Â£)</option>
              <option value="INR">INR (â‚¹)</option>
            </ResponsiveSelect>
          </div>

          <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
            <button type="button" onClick={() => setIsPriceBookModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
              Cancel
            </button>
            <button
              type="submit"
              disabled={createPriceBookMutation.isPending}
              className="flex items-center gap-2 bg-amber-600 hover:bg-amber-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
            >
              {createPriceBookMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Create Price Book
            </button>
          </div>
        </form>
      </ModalShell>

      {/* Adjust Inventory Stock Level Modal */}
      {inventoryProduct && (
        <ModalShell
          isOpen={!!inventoryProduct}
          onClose={() => setInventoryProduct(null)}
          size="md"
          title={
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Boxes className="w-5 h-5 text-indigo-600" />
              Adjust Stock: {inventoryProduct.name}
            </h3>
          }
        >
          <form onSubmit={handleUpdateInventorySubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Stock Delta (+/- Quantity)</label>
              <Input
                type="number"
                required
                value={quantityDelta}
                onChange={(e) => setQuantityDelta(e.target.value)}
                placeholder="e.g. 50 or -10"
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
              <button type="button" onClick={() => setInventoryProduct(null)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                Cancel
              </button>
              <button
                type="submit"
                disabled={updateInventoryMutation.isPending}
                className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
              >
                {updateInventoryMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Update Stock
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* Confirm Delete Modal */}
      {productToDelete && (
        <ConfirmModal
          isOpen={!!productToDelete}
          title="Delete Product"
          description={`Are you sure you want to delete "${productToDelete.name}" from catalog?`}
          confirmText="Delete Product"
          variant="danger"
          onConfirm={handleDeleteProduct}
          onClose={() => setProductToDelete(null)}
        />
      )}
    </div>
  );
}
