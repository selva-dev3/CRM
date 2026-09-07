'use client';

import { useMemo, useState } from 'react';
import { CreditCard, ExternalLink, Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';

import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { useInvoicePaymentSummariesPageQuery, type InvoicePaymentSummary } from '@/lib/api/payments';
import { getErrorMessage } from '@/lib/utils';
import { AddPaymentDialog } from '@/components/features/payments/AddPaymentDialog';
import { useHasPermission } from '@/hooks/use-has-permission';
import { PERMISSIONS } from '@/lib/permissions';

function formatAmount(value: number | string, currency: string): string {
  return new Intl.NumberFormat(undefined, { style: 'currency', currency: currency || 'USD' }).format(Number(value || 0));
}

function formatDate(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

function statusClass(status: string): string {
  if (status === 'Paid') return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (status === 'Partially Paid') return 'bg-blue-50 text-blue-700 border-blue-200';
  return 'bg-amber-50 text-amber-700 border-amber-200';
}

export default function PaymentsPage() {
  const router = useRouter();
  const { hasPermission } = useHasPermission();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const query = useInvoicePaymentSummariesPageQuery({ page, limit: 20, search: search || undefined, status: status || undefined });
  const summaries = query.data?.items ?? [];
  const totalInvoices = query.data?.total ?? 0;

  const columns = useMemo<DataTableColumn<InvoicePaymentSummary>[]>(() => [
    { id: 'payment_number', header: 'Payment', cell: (item) => <div className="min-w-0"><p className="truncate font-semibold text-slate-900" title={item.payment_number || undefined}>{item.payment_number || 'No payment recorded'}</p><p className="text-xs text-slate-500">{item.payment_type && item.latest_payment_amount != null ? `${item.payment_type} · ${formatAmount(item.latest_payment_amount, item.currency)}` : '—'}</p></div> },
    { id: 'invoice', header: 'Invoice', cell: (item) => <button type="button" className="font-semibold text-indigo-600 hover:underline" onClick={(event) => { event.stopPropagation(); router.push(`/invoices/${item.invoice_id}`); }}>{item.invoice_number}</button> },
    { id: 'customer', header: 'Customer', cell: (item) => <div><p className="font-medium text-slate-900">{item.company_name || 'No company'}</p><p className="text-xs text-slate-500">{item.contact_name || item.contact_email || 'No contact'}</p></div> },
    { id: 'amount', header: 'Invoice total', className: 'text-right', cell: (item) => <span className="font-bold text-slate-900">{formatAmount(item.amount, item.currency)}</span> },
    { id: 'paid_amount', header: 'Paid', className: 'text-right', cell: (item) => <span>{formatAmount(item.paid_amount, item.currency)}</span> },
    { id: 'outstanding_amount', header: 'Outstanding', className: 'text-right', cell: (item) => <span>{formatAmount(item.outstanding_amount, item.currency)}</span> },
    { id: 'status', header: 'Status', cell: (item) => <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusClass(item.payment_status)}`}>{item.payment_status}</span> },
    { id: 'paid_at', header: 'Paid date', cell: (item) => <span className="text-sm text-slate-600">{formatDate(item.payment_date)}</span> },
    { id: 'notes', header: 'Notes', cell: (item) => <span>{item.notes || '—'}</span> },
  ], [router]);

  const errorMessage = query.error ? getErrorMessage(query.error, 'Failed to load payments.') : null;

  return (
    <div className="w-full space-y-6 pb-12">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div><h1 className="flex items-center gap-2.5 text-2xl font-bold tracking-tight text-slate-900"><CreditCard className="h-7 w-7 text-indigo-600" /> Payments</h1><p className="mt-0.5 text-sm text-slate-500">Payment status for customer-accepted invoices.</p></div>{hasPermission(PERMISSIONS.INVOICES.PAYMENT) && <AddPaymentDialog />}</div>
      {errorMessage && <div className="flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"><span>{errorMessage}</span><button type="button" className="font-semibold underline" onClick={() => void query.refetch()}>Retry</button></div>}
      <DataTable<InvoicePaymentSummary>
        columns={columns}
        data={summaries}
        getRowKey={(item) => item.id}
        onRowClick={(item) => router.push(item.latest_payment_id ? `/payments/${item.latest_payment_id}` : `/invoices/${item.invoice_id}`)}
        emptyTitle={query.isLoading ? 'Loading payments...' : 'No accepted invoices found'}
        emptyDescription={query.isLoading ? 'Fetching invoice payment statuses.' : 'Customer-accepted invoices will appear here.'}
        searchValue={search}
        onSearchChange={(value) => { setSearch(value); setPage(1); }}
        searchPlaceholder="Search payment, invoice, or customer..."
        toolbarActions={<select aria-label="Payment status" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700"><option value="">All statuses</option><option value="Pending">Pending</option><option value="Partially Paid">Partially Paid</option><option value="Paid">Paid</option></select>}
        isLoading={query.isLoading}
        pagination={{ pageIndex: page - 1, pageCount: Math.max(1, Math.ceil(totalInvoices / 20)), onPageChange: (nextPage) => setPage(nextPage + 1), totalRecords: totalInvoices }}
      />
      {query.isFetching && !query.isLoading && <p className="flex items-center gap-2 text-xs text-slate-500"><Loader2 className="h-3.5 w-3.5 animate-spin" />Refreshing payment records…</p>}
      <p className="flex items-center gap-1 text-xs text-slate-500"><ExternalLink className="h-3.5 w-3.5" />Statuses are calculated from payment records saved by your organization.</p>
    </div>
  );
}
