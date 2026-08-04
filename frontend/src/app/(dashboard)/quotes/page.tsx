'use client';

import React, { useState, useEffect } from 'react';
import { FileCode, Calendar, DollarSign, Building } from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/shared/data-table';
import { useQuotesQuery, QuoteItem } from '@/lib/api/quotes';

export default function QuotesPage() {
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

  const { data: quotes = [], isLoading } = useQuotesQuery(page, limit, debouncedSearchTerm);

  const columns: DataTableColumn<QuoteItem>[] = [
    {
      id: 'quote_number',
      header: 'Quote Ref',
      cell: (item) => (
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100 text-blue-700 font-bold text-xs">
            <FileCode className="w-4 h-4" />
          </div>
          <div>
            <div className="font-semibold text-slate-900">{item.quote_number}</div>
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
      id: 'total_amount',
      header: 'Total Value',
      cell: (item) => (
        <div className="flex items-center gap-1 text-slate-900 font-bold text-xs">
          <DollarSign className="w-3.5 h-3.5 text-slate-500" />
          <span>${item.total_amount.toLocaleString()}</span>
        </div>
      ),
    },
    {
      id: 'status',
      header: 'Status',
      cell: (item) => {
        const s = item.status || 'Draft';
        const badgeStyle =
          s === 'Accepted'
            ? 'bg-emerald-100 text-emerald-700'
            : s === 'Expired'
            ? 'bg-rose-100 text-rose-700'
            : s === 'Sent'
            ? 'bg-blue-100 text-blue-700'
            : 'bg-amber-100 text-amber-700';
        return (
          <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${badgeStyle}`}>
            {s}
          </span>
        );
      },
    },
    {
      id: 'created_at',
      header: 'Issued Date',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-medium">
          <Calendar className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.created_at}</span>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Quotes & Proposals</h1>
          <p className="text-slate-500 text-sm">Create, send, and track price estimates and proposals</p>
        </div>
        <button className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium text-sm cursor-pointer shadow-sm">
          + Create Quote
        </button>
      </div>

      <DataTable<QuoteItem>
        columns={columns}
        data={quotes}
        getRowKey={(item) => item.id}
        emptyTitle="No quotes found"
        emptyDescription="Create a proposal or try searching with a different key."
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search quote ref or client..."
        isLoading={isLoading}
        pagination={{
          pageIndex: page - 1,
          pageCount: quotes.length >= limit ? page + 1 : page,
          onPageChange: (p) => setPage(p + 1),
          totalRecords: (page - 1) * limit + quotes.length,
        }}
      />
    </div>
  );
}
