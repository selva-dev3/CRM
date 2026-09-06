'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, CreditCard, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { usePaymentQuery } from '@/lib/api/payments';
import { getErrorMessage } from '@/lib/utils';

function formatMoney(value: number | string | undefined, currency = 'USD') {
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(Number(value || 0));
}

function formatDate(value?: string | null) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function statusClass(status: string) {
  return status.toLowerCase() === 'failed'
    ? 'border-rose-200 bg-rose-50 text-rose-700'
    : 'border-emerald-200 bg-emerald-50 text-emerald-700';
}

export default function PaymentDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const paymentId = typeof params.id === 'string' ? params.id : '';
  const query = usePaymentQuery(paymentId);
  const payment = query.data;
  const customerName = payment?.customer?.name || payment?.company_name || payment?.contact_name || '—';

  if (query.isLoading) {
    return <div className="flex min-h-80 items-center justify-center gap-2 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" />Loading payment…</div>;
  }

  if (query.isError || !payment) {
    return <div className="space-y-4"><Button variant="ghost" asChild><Link href="/payments"><ArrowLeft className="mr-2 h-4 w-4" />Back to Payments</Link></Button><div className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-800"><p className="font-semibold">Unable to load payment</p><p className="mt-1">{getErrorMessage(query.error, 'The payment was not found or you do not have access to it.')}</p><Button className="mt-4" variant="outline" onClick={() => void query.refetch()}>Retry</Button></div></div>;
  }

  return <div className="w-full space-y-6 pb-12">
    <Button variant="ghost" asChild><Link href="/payments"><ArrowLeft className="mr-2 h-4 w-4" />Back to Payments</Link></Button>
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div><p className="flex items-center gap-2 text-sm font-medium text-indigo-600"><CreditCard className="h-4 w-4" />Payment detail</p><h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">{payment.payment_number}</h1><p className="mt-1 text-sm text-slate-500">Recorded against invoice {payment.invoice_number}</p></div><span className={`w-fit rounded-full border px-3 py-1 text-xs font-semibold ${statusClass(payment.status)}`}>{payment.status}</span></div>
    <div className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="text-base font-semibold text-slate-900">Payment information</h2><dl className="mt-5 grid gap-5 sm:grid-cols-2">{[['Amount', formatMoney(payment.amount, payment.currency)], ['Currency', payment.currency], ['Payment type', payment.payment_type], ['Payment date', formatDate(payment.payment_date)], ['Created date', formatDate(payment.created_at)], ['Notes', payment.notes || '—']].map(([label, value]) => <div key={label}><dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt><dd className="mt-1 break-words text-sm font-medium text-slate-900">{value}</dd></div>)}</dl></section>
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="text-base font-semibold text-slate-900">Invoice and customer</h2><dl className="mt-5 space-y-5"><div><dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Invoice</dt><dd className="mt-1"><Link className="font-semibold text-indigo-600 hover:underline" href={`/invoices/${payment.invoice_id}`}>{payment.invoice_number}</Link></dd></div><div><dt className="text-xs font-medium uppercase tracking-wide text-slate-500">Customer</dt><dd className="mt-1 text-sm font-medium text-slate-900">{customerName}</dd>{payment.contact_email && <p className="text-sm text-slate-500">{payment.contact_email}</p>}</div><div className="grid grid-cols-2 gap-4"><div><dt className="text-xs text-slate-500">Invoice total</dt><dd className="mt-1 text-sm font-semibold">{formatMoney(payment.invoice_total, payment.currency)}</dd></div><div><dt className="text-xs text-slate-500">Total paid</dt><dd className="mt-1 text-sm font-semibold">{formatMoney(payment.invoice_paid_amount, payment.currency)}</dd></div><div><dt className="text-xs text-slate-500">Outstanding</dt><dd className="mt-1 text-sm font-semibold text-amber-700">{formatMoney(payment.invoice_outstanding_amount, payment.currency)}</dd></div><div><dt className="text-xs text-slate-500">Invoice status</dt><dd className="mt-1 text-sm font-semibold">{payment.invoice_payment_status || 'Pending'}</dd></div></div></dl></section>
    </div>
    <Button variant="outline" onClick={() => router.push('/payments')}>Return to payments</Button>
  </div>;
}
