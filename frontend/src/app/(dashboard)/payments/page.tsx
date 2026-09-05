'use client';

import { useMemo, useState } from 'react';
import { CreditCard, ExternalLink, Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';

import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { usePaymentsQuery, type PaymentItem } from '@/lib/api/payments';
import { getErrorMessage } from '@/lib/utils';

function formatAmount(payment: PaymentItem): string {
  return new Intl.NumberFormat(undefined, { style: 'currency', currency: payment.currency || 'USD' }).format(payment.amount || 0);
}

function formatDate(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

function statusClass(status: string): string {
  if (status.toLowerCase() === 'succeeded') return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (status.toLowerCase() === 'failed') return 'bg-rose-50 text-rose-700 border-rose-200';
  return 'bg-amber-50 text-amber-700 border-amber-200';
}

export default function PaymentsPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const query = usePaymentsQuery({ page, limit: 20, search: search || undefined, status: status || undefined });
  const payments = query.data ?? [];

  const columns = useMemo<DataTableColumn<PaymentItem>[]>(() => [
    { id: 'id', header: 'Payment', cell: (item) => <div className="min-w-0"><p className="truncate font-semibold text-slate-900" title={item.id}>{item.id}</p><p className="text-xs text-slate-500">{item.provider} · {item.payment_method || 'Method unavailable'}</p></div> },
    { id: 'invoice', header: 'Invoice', cell: (item) => <button type="button" className="font-semibold text-indigo-600 hover:underline" onClick={(event) => { event.stopPropagation(); router.push(`/invoices/${item.invoice_id}`); }}>{item.invoice_number}</button> },
    { id: 'customer', header: 'Customer', cell: (item) => <div><p className="font-medium text-slate-900">{item.company_name || 'No company'}</p><p className="text-xs text-slate-500">{item.contact_name || item.contact_email || 'No contact'}</p></div> },
    { id: 'amount', header: 'Amount', className: 'text-right', cell: (item) => <span className="font-bold text-slate-900">{formatAmount(item)}</span> },
    { id: 'status', header: 'Status', cell: (item) => <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusClass(item.status)}`}>{item.status}</span> },
    { id: 'paid_at', header: 'Paid date', cell: (item) => <span className="text-sm text-slate-600">{formatDate(item.paid_at)}</span> },
    { id: 'provider_payment_id', header: 'Transaction', cell: (item) => <span className="block max-w-[180px] truncate font-mono text-xs text-slate-500" title={item.provider_payment_id}>{item.provider_payment_id}</span> },
  ], [router]);

  const errorMessage = query.error ? getErrorMessage(query.error, 'Failed to load payments.') : null;

  return (
    <div className="w-full space-y-6 pb-12">
      <div><h1 className="flex items-center gap-2.5 text-2xl font-bold tracking-tight text-slate-900"><CreditCard className="h-7 w-7 text-indigo-600" /> Payments</h1><p className="mt-0.5 text-sm text-slate-500">Verified provider payments recorded for your organization.</p></div>
      {errorMessage && <div className="flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"><span>{errorMessage}</span><button type="button" className="font-semibold underline" onClick={() => void query.refetch()}>Retry</button></div>}
      <DataTable<PaymentItem>
        columns={columns}
        data={payments}
        getRowKey={(item) => item.id}
        onRowClick={(item) => router.push(`/invoices/${item.invoice_id}`)}
        emptyTitle={query.isLoading ? 'Loading payments...' : 'No payments found'}
        emptyDescription={query.isLoading ? 'Fetching verified payment records.' : 'Payments will appear here after a verified provider webhook.'}
        searchValue={search}
        onSearchChange={(value) => { setSearch(value); setPage(1); }}
        searchPlaceholder="Search payment, invoice, or customer..."
        toolbarActions={<select aria-label="Payment status" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700"><option value="">All statuses</option><option value="Succeeded">Succeeded</option><option value="Failed">Failed</option></select>}
        isLoading={query.isLoading}
        pagination={{ pageIndex: page - 1, pageCount: payments.length >= 20 ? page + 1 : page, onPageChange: (nextPage) => setPage(nextPage + 1), totalRecords: (page - 1) * 20 + payments.length }}
      />
      {query.isFetching && !query.isLoading && <p className="flex items-center gap-2 text-xs text-slate-500"><Loader2 className="h-3.5 w-3.5 animate-spin" />Refreshing payment records…</p>}
      <p className="flex items-center gap-1 text-xs text-slate-500"><ExternalLink className="h-3.5 w-3.5" />Payment status is read-only and comes from verified backend provider events.</p>
    </div>
  );
}
