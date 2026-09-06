'use client';

import { Input } from "@/components/ui/input";

import { InvoiceItemsTable } from '@/components/features/invoices/InvoiceItemsTable';
import { formatInvoiceMoney } from '@/lib/formatters/invoice';
import { formatDate } from '@/lib/formatters/date';
import { useHasPermission } from '@/hooks/use-has-permission';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';
import React, { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Receipt,
  Calendar,
  Send,
  CheckCircle2,
  AlertCircle,
  X,
  Loader2,
  Trash2,
  Download,
  CreditCard,
  BellRing,
} from 'lucide-react';
import { ActionMenu } from '@/components/common/action-menu';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ModalShell } from '@/components/common/modal-shell';
import {
  useInvoiceQuery,
  useInvoicePdfQuery,
  useSendInvoiceEmailMutation,
  useSendPaymentReminderMutation,
  useDeleteInvoiceMutation
} from '@/lib/api/invoices';
import { InvoiceWorkflowActions } from '@/components/features/invoices/InvoiceWorkflowActions';
import { InvoiceSummary } from '@/components/features/invoices/InvoiceSummary';
import { usePaymentsQuery } from '@/lib/api/payments';

export default function InvoiceDetailPage() {
  const { hasPermission } = useHasPermission();
  const params = useParams();
  const router = useRouter();
  const invoiceId = (params?.id as string) || '';

  // Queries
  const { data: invoice, isLoading, isError, isFetching, refetch } = useInvoiceQuery(invoiceId, {
    refetchInterval: (query) => query.state.data?.delivery_status === 'Pending' ? 5000 : false,
  });
  const paymentsQuery = usePaymentsQuery({ invoice_id: invoiceId }, { enabled: Boolean(invoiceId) });
  const { data: pdfData } = useInvoicePdfQuery(invoiceId, {
    enabled: Boolean(invoice?.pdf_available),
  });

  // Mutations
  const sendEmailMutation = useSendInvoiceEmailMutation();
  const reminderMutation = useSendPaymentReminderMutation();
  const deleteMutation = useDeleteInvoiceMutation();

  // State
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isSendEmailModalOpen, setIsSendEmailModalOpen] = useState(false);
  const [recipientEmailInput, setRecipientEmailInput] = useState('');

  // Toast / Alert notifications
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSendEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recipientEmailInput.trim()) return;
    try {
      await sendEmailMutation.mutateAsync({ id: invoiceId, recipient_email: recipientEmailInput.trim() });
      setSuccessMessage(`Invoice email queued for ${recipientEmailInput.trim()}.`);
      setIsSendEmailModalOpen(false);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to send invoice email.'));
    }
  };


  const handleSendReminder = async () => {
    try {
      await reminderMutation.mutateAsync(invoiceId);
      setSuccessMessage('Payment reminder queued for the client.');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to send payment reminder.'));
    }
  };

  const handleDeleteInvoice = async () => {
    try {
      await deleteMutation.mutateAsync(invoiceId);
      router.push('/invoices');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to delete invoice.'));
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-2 text-slate-500">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
          <span className="text-sm font-medium">Loading invoice details...</span>
        </div>
      </div>
    );
  }

  if (!invoice) {
    return (
      <div className="p-6 max-w-2xl mx-auto space-y-4">
        <Link href="/invoices" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900 font-medium">
          <ArrowLeft className="w-4 h-4" />
          Back to Invoices
        </Link>
        <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 space-y-2">
          <div className="flex items-center gap-2 font-bold text-base">
            <AlertCircle className="w-5 h-5 text-rose-600" />
            Unable to load invoice
          </div>
          <p className="text-sm">The invoice could not be loaded. Please retry.</p>
          <Button onClick={() => void refetch()}>Retry</Button>
        </div>
      </div>
    );
  }

  const s = invoice.status || 'Draft';
  const badgeStyle =
    s === 'Accepted'
      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
      : s === 'Cancelled'
      ? 'bg-rose-50 text-rose-700 border-rose-200'
      : s === 'Draft'
      ? 'bg-slate-100 text-slate-700 border-slate-200'
      : 'bg-amber-50 text-amber-700 border-amber-200';

  return (
    <div className="space-y-6 w-full pb-12">
      {/* Navigation & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <Link href="/invoices" className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-indigo-600 transition-colors">
            <ArrowLeft className="w-4 h-4" />
            Back to Invoices & Billing
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
              <Receipt className="w-6 h-6 text-indigo-600" />
              Invoice: {invoice.invoice_number}
            </h1>
            <span className={`px-3 py-0.5 rounded-full text-xs font-semibold border ${badgeStyle}`}>
              {s}
            </span>
          </div>
        </div>

        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <InvoiceWorkflowActions invoice={invoice} />

          {['Finalized', 'Accepted'].includes(s) && hasPermission(PERMISSIONS.INVOICES.SEND) && <Button
            onClick={() => {
              setRecipientEmailInput(invoice.recipient_email || (typeof invoice.billing_snapshot?.email === 'string' ? invoice.billing_snapshot.email : ''));
              setIsSendEmailModalOpen(true);
            }}
            className="w-full gap-2 text-xs font-semibold sm:w-auto"
          >
            <Send className="w-4 h-4" />
            Send Invoice
          </Button>}

          {pdfData?.pdf_url && (
            <Button asChild variant="outline" className="w-full gap-2 text-xs font-semibold sm:w-auto">
              <a href={pdfData.pdf_url} target="_blank" rel="noopener noreferrer">
                <Download className="w-4 h-4 text-indigo-600" />
                Download PDF
              </a>
            </Button>
          )}

          <ActionMenu
            label="More"
            className="w-full text-xs font-semibold sm:w-auto"
            actions={invoice.payment_status !== 'Paid' && ['Finalized', 'Accepted'].includes(s) ? [
              {
                label: 'Send reminder',
                icon: <BellRing className="w-4 h-4 text-amber-500" />,
                onSelect: handleSendReminder,
              },
              {
                label: 'Delete invoice',
                icon: <Trash2 className="w-4 h-4" />,
                variant: 'destructive',
                onSelect: () => setIsDeleteModalOpen(true),
              },
            ] : [
              {
                label: 'Delete invoice',
                icon: <Trash2 className="w-4 h-4" />,
                variant: 'destructive',
                onSelect: () => setIsDeleteModalOpen(true),
              },
            ]}
          />
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

      {s === 'Finalized' && !invoice.accepted_at && <p role="status">Waiting for customer acceptance.</p>}

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Line Items & Totals */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-6">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3">
              Invoice Items & Payment Details
            </h3>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 pb-4 border-b border-slate-100">
              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Due Date</span>
                <div className="flex items-center gap-2 font-semibold text-sm text-slate-900">
                  <Calendar className="w-4 h-4 text-slate-400" />
                  <span>{formatDate(invoice.due_date, { fallback: 'Not set' })}</span>
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Invoice Amount</span>
                <div className="flex items-center gap-1 text-emerald-600 font-bold text-base">
                  <span>{formatInvoiceMoney(invoice.amount, invoice.currency)}</span>
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Payment Status</span>
                <div className="text-slate-900 font-semibold text-sm">
                  {invoice.payment_status || 'Pending'}
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Delivery</span>
                <div className="text-slate-900 font-semibold text-sm">
                  {sendEmailMutation.isPending ? 'Queueing…' : isFetching ? 'Loading delivery status…' : isError ? 'Unknown — refresh failed' : invoice.delivery_status || 'Unknown'}
                  {isError && <Button variant="outline" onClick={() => void refetch()}>Retry delivery status</Button>}
                </div>
              </div>
            </div>

            <InvoiceItemsTable items={invoice.items} currency={invoice.currency} />

            <InvoiceSummary invoice={invoice} />
          </div>
        </div>

      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-center justify-between gap-3 border-b border-slate-100 pb-3">
          <h2 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-slate-900"><CreditCard className="h-4 w-4 text-indigo-600" /> Recorded payments</h2>
          <span className="text-xs text-slate-500">Manual payment receipts</span>
        </div>
        {paymentsQuery.isLoading ? <p className="text-sm text-slate-500">Loading payment records…</p> : paymentsQuery.isError ? <div className="flex items-center justify-between gap-3 text-sm text-rose-700"><span>Payment records could not be loaded.</span><button type="button" className="font-semibold underline" onClick={() => void paymentsQuery.refetch()}>Retry</button></div> : paymentsQuery.data?.length ? <div className="overflow-x-auto"><Table className="min-w-[680px] text-xs"><TableHeader><TableRow><TableHead>Payment ID</TableHead><TableHead>Amount</TableHead><TableHead>Method</TableHead><TableHead>Status</TableHead><TableHead>Notes</TableHead><TableHead>Paid date</TableHead></TableRow></TableHeader><TableBody>{paymentsQuery.data.map((payment) => <TableRow key={payment.id}><TableCell className="font-mono">{payment.payment_number}</TableCell><TableCell className="font-semibold">{payment.currency} {Number(payment.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}</TableCell><TableCell>{payment.payment_type || 'Unavailable'}</TableCell><TableCell>{payment.status}</TableCell><TableCell className="max-w-[180px] truncate font-mono" title={payment.notes || undefined}>{payment.notes}</TableCell><TableCell>{payment.payment_date || payment.paid_at || payment.created_at || '—'}</TableCell></TableRow>)}</TableBody></Table></div> : <p className="text-sm text-slate-500">No payments have been recorded for this invoice.</p>}
      </section>

      {/* Send Email Modal */}
      {isSendEmailModalOpen && (
        <ModalShell
          isOpen={isSendEmailModalOpen}
          onClose={() => setIsSendEmailModalOpen(false)}
          title={
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Send className="w-5 h-5 text-blue-600" />
              Email Invoice
            </h3>
          }
        >
          <form onSubmit={handleSendEmailSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Recipient Email Address *</label>
              <Input
                type="email"
                required
                value={recipientEmailInput}
                onChange={(e) => setRecipientEmailInput(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
              <button type="button" onClick={() => setIsSendEmailModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                Cancel
              </button>
              <button
                type="submit"
                disabled={sendEmailMutation.isPending}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
              >
                {sendEmailMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Send Email
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* Delete Confirm Modal */}
      {isDeleteModalOpen && (
        <ConfirmModal
          isOpen={isDeleteModalOpen}
          title="Delete Invoice"
          description={`Are you sure you want to delete invoice "${invoice.invoice_number}"?`}
          confirmText="Delete Invoice"
          variant="danger"
          onConfirm={handleDeleteInvoice}
          onClose={() => setIsDeleteModalOpen(false)}
        />
      )}
    </div>
  );
}
