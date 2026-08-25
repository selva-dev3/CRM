'use client';

import React, { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Package,
  Tag,
  DollarSign,
  Layers,
  Boxes,
  MapPin,
  CheckCircle2,
  AlertCircle,
  X,
  Loader2,
  Trash2,
  Edit,
  ShieldCheck
} from 'lucide-react';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { ModalShell } from '@/components/common/modal-shell';
import {
  useProductQuery,
  useProductInventoryQuery,
  useDeleteProductMutation,
  useUpdateProductInventoryMutation
} from '@/lib/api/products';

export default function ProductDetailPage() {
  const params = useParams();
  const router = useRouter();
  const productId = (params?.id as string) || '';

  // Queries
  const { data: product, isLoading, isError } = useProductQuery(productId);
  const { data: inventory } = useProductInventoryQuery(productId);

  // Mutations
  const deleteMutation = useDeleteProductMutation();
  const updateInventoryMutation = useUpdateProductInventoryMutation();

  // State
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [quantityDelta, setQuantityDelta] = useState('10');
  const [isStockModalOpen, setIsStockModalOpen] = useState(false);

  // Toast / Alert notifications
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleDeleteProduct = async () => {
    try {
      await deleteMutation.mutateAsync(productId);
      router.push('/products');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete product.');
    }
  };

  const handleUpdateStockSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const delta = parseInt(quantityDelta || '0', 10);
    try {
      await updateInventoryMutation.mutateAsync({ id: productId, delta });
      setSuccessMessage(`Inventory updated by ${delta} units.`);
      setIsStockModalOpen(false);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to update inventory.');
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-2 text-slate-500">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
          <span className="text-sm font-medium">Loading product details...</span>
        </div>
      </div>
    );
  }

  if (isError || !product) {
    return (
      <div className="p-6 max-w-2xl mx-auto space-y-4">
        <Link href="/products" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900 font-medium">
          <ArrowLeft className="w-4 h-4" />
          Back to Product Catalog
        </Link>
        <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 space-y-2">
          <div className="flex items-center gap-2 font-bold text-base">
            <AlertCircle className="w-5 h-5 text-rose-600" />
            Product Not Found
          </div>
          <p className="text-sm">The product you requested could not be found or may have been deleted.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 w-full pb-12">
      {/* Navigation & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <Link href="/products" className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-indigo-600 transition-colors">
            <ArrowLeft className="w-4 h-4" />
            Back to Product Catalog
          </Link>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-3">
            <Package className="w-6 h-6 text-indigo-600" />
            {product.name}
          </h1>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={() => setIsStockModalOpen(true)}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-3.5 py-2 rounded-lg text-sm font-semibold transition-colors cursor-pointer shadow-sm"
          >
            <Boxes className="w-4 h-4" />
            Adjust Inventory Stock
          </button>

          <button
            onClick={() => setIsDeleteModalOpen(true)}
            className="flex items-center gap-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 px-3.5 py-2 rounded-lg text-sm font-semibold transition-colors cursor-pointer"
          >
            <Trash2 className="w-4 h-4" />
            Delete Product
          </button>
        </div>
      </div>

      {/* Toast Feedback */}
      {successMessage && (
        <div className="flex items-center justify-between p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl shadow-sm">
          <div className="flex items-center gap-2 text-sm font-medium">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            <span>{successMessage}</span>
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

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Product Specifications & Pricing */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-6">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3">
              Product Specifications & Pricing
            </h3>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">SKU Identifier</span>
                <div className="flex items-center gap-2 font-mono font-bold text-sm text-slate-900">
                  <Tag className="w-4 h-4 text-indigo-600" />
                  <span>{product.sku}</span>
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">List Price</span>
                <div className="flex items-center gap-1 text-emerald-600 font-bold text-base">
                  <DollarSign className="w-4 h-4 text-emerald-500" />
                  <span>{product.price ? product.price.toLocaleString(undefined, { minimumFractionDigits: 2 }) : '0.00'}</span>
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Category</span>
                <div className="text-slate-900 font-semibold text-sm">
                  {product.category || 'Software'}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Inventory & Stock History */}
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3 flex items-center gap-2">
              <Boxes className="w-4 h-4 text-indigo-600" />
              Inventory & Warehouse
            </h3>

            <div className="space-y-3">
              <div className="p-4 bg-indigo-50/60 border border-indigo-100 rounded-xl flex items-center justify-between">
                <div>
                  <span className="text-xs font-semibold text-indigo-700 block uppercase tracking-wider">Available Stock</span>
                  <h4 className="text-xl font-extrabold text-indigo-950 mt-0.5">
                    {inventory?.in_stock_quantity ?? product.in_stock_quantity ?? 100} Units
                  </h4>
                </div>
                <div className="h-10 w-10 rounded-full bg-indigo-100 text-indigo-700 font-bold flex items-center justify-center">
                  <Boxes className="w-5 h-5" />
                </div>
              </div>

              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-1 text-xs">
                <span className="text-slate-500 font-medium block">Reorder Level Threshold:</span>
                <span className="font-bold text-slate-900">{inventory?.reorder_level || 50} Units</span>
              </div>

              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-1 text-xs">
                <span className="text-slate-500 font-medium block flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-slate-400" />
                  Warehouse Location:
                </span>
                <span className="font-semibold text-slate-800">{inventory?.warehouse_location || 'Main Warehouse Section A-4'}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Adjust Stock Modal */}
      {isStockModalOpen && (
        <ModalShell
          isOpen={isStockModalOpen}
          onClose={() => setIsStockModalOpen(false)}
          size="md"
          title={
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Boxes className="w-5 h-5 text-indigo-600" />
              Adjust Stock Quantity
            </h3>
          }
        >
          <form onSubmit={handleUpdateStockSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Quantity Delta (+/-)</label>
              <input
                type="number"
                required
                value={quantityDelta}
                onChange={(e) => setQuantityDelta(e.target.value)}
                placeholder="e.g. 25 or -10"
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-3 pt-2">
              <button type="button" onClick={() => setIsStockModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                Cancel
              </button>
              <button
                type="submit"
                disabled={updateInventoryMutation.isPending}
                className="flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
              >
                {updateInventoryMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Save Adjustment
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* Delete Confirm Modal */}
      {isDeleteModalOpen && (
        <ConfirmModal
          isOpen={isDeleteModalOpen}
          title="Delete Product"
          description={`Are you sure you want to delete "${product.name}"?`}
          confirmText="Delete Product"
          variant="danger"
          onConfirm={handleDeleteProduct}
          onClose={() => setIsDeleteModalOpen(false)}
        />
      )}
    </div>
  );
}
