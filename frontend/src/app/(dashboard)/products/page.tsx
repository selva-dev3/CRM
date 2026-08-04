'use client';

import React, { useState, useEffect } from 'react';
import { Package, Tag, DollarSign, Layers } from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/shared/data-table';
import { useProductsQuery, ProductItem } from '@/lib/api/products';

export default function ProductsPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [page, setPage] = useState(1);
  const limit = 15;

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
      setPage(1);
    }, 250);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  const { data: products = [], isLoading } = useProductsQuery(page, limit, debouncedSearchTerm);

  const columns: DataTableColumn<ProductItem>[] = [
    {
      id: 'name',
      header: 'Product Name',
      cell: (item) => (
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-100 text-emerald-700 font-bold text-xs">
            <Package className="w-4 h-4" />
          </div>
          <div>
            <div className="font-semibold text-slate-900">{item.name}</div>
            <div className="text-xs text-slate-500">{item.sku}</div>
          </div>
        </div>
      ),
    },
    {
      id: 'sku',
      header: 'SKU Identifier',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-mono font-bold">
          <Tag className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.sku}</span>
        </div>
      ),
    },
    {
      id: 'price',
      header: 'Price (USD)',
      cell: (item) => (
        <div className="flex items-center gap-1 text-emerald-600 font-bold text-xs">
          <DollarSign className="w-3.5 h-3.5 text-emerald-500" />
          <span>{item.price.toLocaleString()}</span>
        </div>
      ),
    },
    {
      id: 'category',
      header: 'Category Tier',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-medium">
          <Layers className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.category || 'Software'}</span>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Product Catalog</h1>
          <p className="text-slate-500 text-sm">Manage products, pricing tiers, and SKUs</p>
        </div>
        <button className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium text-sm cursor-pointer shadow-sm">
          + Add Product
        </button>
      </div>

      <DataTable<ProductItem>
        columns={columns}
        data={products}
        getRowKey={(item) => item.id}
        emptyTitle="No products found"
        emptyDescription="Add products or adjust your search filter."
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search product name or SKU..."
        isLoading={isLoading}
        pagination={{
          pageIndex: page - 1,
          pageCount: products.length >= limit ? page + 1 : page,
          onPageChange: (p) => setPage(p + 1),
          totalRecords: (page - 1) * limit + products.length,
        }}
      />
    </div>
  );
}
