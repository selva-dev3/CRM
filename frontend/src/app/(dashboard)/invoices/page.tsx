'use client';

import React, { useState, useEffect } from 'react';
import { FileText, Calendar, DollarSign, Building } from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/shared/data-table';
import { useInvoicesQuery, InvoiceItem } from '@/lib/api/invoices';

export default function InvoicesPage() {
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

  const { data: invoices = [], isLoading } = useInvoicesQuery(page, limit, debouncedSearchTerm);

  const columns: DataTableColumn<InvoiceItem>[] = [
    {
      id: 'number',
      header: 'Invoice Number',
      cell: (item) => (
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-100 text-purple-700 font-bold text-xs">
            <FileText className="w-4 h-4" />
          </div>
          <div>
            <div className="font-semibold text-slate-900">{item.number}</div>
            <div className="text-xs text-slate-500">{item.client}</div>
          </div>
        </div>
      ),
    },
    {
      id: 'client',
      header: 'Client Account',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-medium">
          <Building className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.client}</span>
        </div>
      ),
    },
    {
      id: 'amount',
      header: 'Invoice Total',
      cell: (item) => (
        <div className="flex items-center gap-1 text-slate-900 font-bold text-xs">
          <DollarSign className="w-3.5 h-3.5 text-slate-500" />
          <span>${item.amount.toLocaleString()}</span>
        </div>
      ),
    },
    {
      id: 'status',
      header: 'Payment Status',
      cell: (item) => {
        const s = item.status || 'Pending';
        const badgeStyle =
          s === 'Paid'
            ? 'bg-emerald-100 text-emerald-700'
            : s === 'Overdue'
            ? 'bg-rose-100 text-rose-700'
            : s === 'Draft'
            ? 'bg-slate-100 text-slate-700'
            : 'bg-amber-100 text-amber-700';
        return (
          <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${badgeStyle}`}>
            {s}
          </span>
        );
      },
    },
    {
      id: 'due_date',
      header: 'Due Date',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-medium">
          <Calendar className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.due_date}</span>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Invoices & Billing</h1>
          <p className="text-slate-500 text-sm">Generate invoices and collect payments via Stripe</p>
        </div>
        <button className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium text-sm cursor-pointer shadow-sm">
          + Generate Invoice
        </button>
      </div>

      <DataTable<InvoiceItem>
        columns={columns}
        data={invoices}
        getRowKey={(item) => item.id}
        emptyTitle="No invoices found"
        emptyDescription="Create an invoice or refine your search query."
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search invoice number or client..."
        isLoading={isLoading}
        pagination={{
          pageIndex: page - 1,
          pageCount: invoices.length >= limit ? page + 1 : page,
          onPageChange: (p) => setPage(p + 1),
          totalRecords: (page - 1) * limit + invoices.length,
        }}
      />
    </div>
  );
}
