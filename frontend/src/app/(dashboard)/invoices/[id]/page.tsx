'use client';

import React, { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Receipt,
  Calendar,
  DollarSign,
  Send,
  CheckCircle2,
  AlertCircle,
  X,
  Loader2,
  Trash2,
  Download,
  CreditCard,
  BellRing,
  ShieldCheck,
  Zap,
  Percent
} from 'lucide-react';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { ModalShell } from '@/components/common/modal-shell';
import {
  useInvoiceQuery,
  useInvoicePdfQuery,
  useSendInvoiceEmailMutation,
  useCreateStripeCheckoutMutation,
  useMarkInvoicePaidMutation,
  useSendPaymentReminderMutation,
  useIssueCreditMemoMutation,
  useDeleteInvoiceMutation
} from '@/lib/api/invoices';

export default function InvoiceDetailPage() {
  const params = useParams();
  const router = useRouter();
  const invoiceId = (params?.id as string) || '';

  // Queries
  const { data: invoice, isLoading, isError } = useInvoiceQuery(invoiceId);
  const { data: pdfData } = useInvoicePdfQuery(invoiceId);

  // Mutations
  const sendEmailMutation = useSendInvoiceEmailMutation();
  const stripeCheckoutMutation = useCreateStripeCheckoutMutation();
  const markPaidMutation = useMarkInvoicePaidMutation();
  const reminderMutation = useSendPaymentReminderMutation();
  const creditMemoMutation = useIssueCreditMemoMutation();
  const deleteMutation = useDeleteInvoiceMutation();

  // State
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isSendEmailModalOpen, setIsSendEmailModalOpen] = useState(false);
  const [isCreditMemoModalOpen, setIsCreditMemoModalOpen] = useState(false);
  const [recipientEmailInput, setRecipientEmailInput] = useState('billing@client.com');
  const [creditMemoAmount, setCreditMemoAmount] = useState('500');
  const [creditMemoReason, setCreditMemoReason] = useState('Service credit discount');

  // Toast / Alert notifications
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSendEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recipientEmailInput.trim()) return;
    try {
      await sendEmailMutation.mutateAsync({ id: invoiceId, recipient_email: recipientEmailInput.trim() });
      setSuccessMessage(`Invoice email sent to ${recipientEmailInput.trim()}.`);
      setIsSendEmailModalOpen(false);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to send invoice email.');
    }
  };

  const handleStripeCheckout = async () => {
    try {
      const res = await stripeCheckoutMutation.mutateAsync(invoiceId);
      setSuccessMessage('Stripe Checkout session generated.');
      window.open(res.checkout_url, '_blank');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to launch Stripe Checkout.');
    }
  };

  const handleMarkPaid = async () => {
    try {
      await markPaidMutation.mutateAsync({ id: invoiceId, payment_method: 'Stripe Online' });
      setSuccessMessage('Invoice marked as Paid.');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to mark invoice as paid.');
    }
  };

  const handleSendReminder = async () => {
    try {
      await reminderMutation.mutateAsync(invoiceId);
      setSuccessMessage('Payment reminder email sent to client.');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to send payment reminder.');
    }
  };

  const handleCreditMemoSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const amt = parseFloat(creditMemoAmount || '0');
    try {
      await creditMemoMutation.mutateAsync({ id: invoiceId, amount: amt, reason: creditMemoReason });
      setSuccessMessage(`Credit memo of $${amt} issued against invoice.`);
      setIsCreditMemoModalOpen(false);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to issue credit memo.');
    }
  };

  const handleDeleteInvoice = async () => {
    try {
      await deleteMutation.mutateAsync(invoiceId);
      router.push('/invoices');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete invoice.');
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

  if (isError || !invoice) {
    return (
      <div className="p-6 max-w-2xl mx-auto space-y-4">
        <Link href="/invoices" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900 font-medium">
          <ArrowLeft className="w-4 h-4" />
          Back to Invoices
        </Link>
        <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 space-y-2">
          <div className="flex items-center gap-2 font-bold text-base">
            <AlertCircle className="w-5 h-5 text-rose-600" />
            Invoice Not Found
          </div>
          <p className="text-sm">The invoice you requested could not be found or may have been deleted.</p>
        </div>
      </div>
    );
  }

  const s = invoice.status || 'Pending';
  const badgeStyle =
    s === 'Paid'
      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
      : s === 'Overdue'
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

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={handleStripeCheckout}
            disabled={stripeCheckoutMutation.isPending}
            className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-3.5 py-2 rounded-lg text-xs font-semibold transition-colors cursor-pointer shadow-xs disabled:opacity-50"
          >
            {stripeCheckoutMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <CreditCard className="w-4 h-4" />}
            Stripe Checkout
          </button>

          {pdfData?.pdf_url && (
            <a
              href={pdfData.pdf_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg text-xs font-semibold shadow-xs"
            >
              <Download className="w-4 h-4 text-indigo-600" />
              Download PDF
            </a>
          )}

          <button
            onClick={() => setIsSendEmailModalOpen(true)}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-3.5 py-2 rounded-lg text-xs font-semibold transition-colors cursor-pointer shadow-xs"
          >
            <Send className="w-4 h-4" />
            Send Email
          </button>

          {s !== 'Paid' && (
            <>
              <button
                onClick={handleSendReminder}
                className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg text-xs font-semibold shadow-xs cursor-pointer"
              >
                <BellRing className="w-4 h-4 text-amber-500" />
                Send Reminder
              </button>

              <button
                onClick={handleMarkPaid}
                className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-3.5 py-2 rounded-lg text-xs font-semibold transition-colors cursor-pointer shadow-xs"
              >
                <CheckCircle2 className="w-4 h-4" />
                Mark Paid
              </button>
            </>
          )}

          <button
            onClick={() => setIsCreditMemoModalOpen(true)}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg text-xs font-semibold shadow-xs cursor-pointer"
          >
            <Percent className="w-4 h-4 text-purple-600" />
            Credit Memo
          </button>

          <button
            onClick={() => setIsDeleteModalOpen(true)}
            className="flex items-center gap-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 px-3 py-2 rounded-lg text-xs font-semibold shadow-xs cursor-pointer"
          >
            <Trash2 className="w-4 h-4" />
            Delete
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
          <button onClick={() => setSuccessMessage(null)} className="text-emerald-600 hover:text-emerald-800">
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
          <button onClick={() => setErrorMessage(null)} className="text-rose-600 hover:text-rose-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

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
                  <span>{invoice.due_date ? invoice.due_date.substring(0, 10) : '2026-09-01'}</span>
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Invoice Amount</span>
                <div className="flex items-center gap-1 text-emerald-600 font-bold text-base">
                  <DollarSign className="w-4 h-4 text-emerald-500" />
                  <span>{invoice.amount ? invoice.amount.toLocaleString(undefined, { minimumFractionDigits: 2 }) : '0.00'}</span>
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Payment Status</span>
                <div className="text-slate-900 font-semibold text-sm">
                  {invoice.status || 'Pending'}
                </div>
              </div>
            </div>

            {/* Line Items (present on invoices generated from a Closed Won deal) */}
            {invoice.items && invoice.items.length > 0 && (
              <div className="space-y-2 pb-2">
                <span className="text-xs font-bold text-slate-800 uppercase tracking-wider block">Line Items</span>
                <div className="overflow-x-auto -mx-1">
                  <table className="w-full text-xs min-w-[420px]">
                    <thead>
                      <tr className="text-left text-slate-400 uppercase tracking-wider">
                        <th className="py-2 px-1 font-semibold">Description</th>
                        <th className="py-2 px-1 font-semibold text-right">Qty</th>
                        <th className="py-2 px-1 font-semibold text-right">Unit Price</th>
                        <th className="py-2 px-1 font-semibold text-right">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {invoice.items.map((item) => (
                        <tr key={item.id} className="text-slate-700">
                          <td className="py-2 px-1 font-medium">{item.description || item.product_id}</td>
                          <td className="py-2 px-1 text-right">{item.quantity}</td>
                          <td className="py-2 px-1 text-right">${(item.unit_price || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                          <td className="py-2 px-1 text-right font-bold text-slate-900">
                            ${((item.quantity || 0) * (item.unit_price || 0)).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
              <span className="text-xs font-bold text-slate-800 uppercase tracking-wider block">Stripe Online Payment URL</span>
              <a
                href={invoice.stripe_checkout_url || `https://checkout.stripe.com/pay/${invoice.id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-mono text-indigo-600 hover:underline break-all block"
              >
                {invoice.stripe_checkout_url || `https://checkout.stripe.com/pay/${invoice.id}`}
              </a>
            </div>
          </div>
        </div>

        {/* Right Column: Stripe Gateway Status */}
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-purple-600" />
              Stripe Gateway Protection
            </h3>

            <div className="p-4 bg-purple-50/50 border border-purple-100 rounded-xl space-y-2">
              <span className="text-xs font-bold text-purple-900 block">PCI-DSS Compliant</span>
              <p className="text-xs text-purple-800 leading-relaxed font-medium">
                Clients can securely settle invoices via Credit Card, Apple Pay, Google Pay, or ACH Direct Debit.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Credit Memo Modal */}
      {isCreditMemoModalOpen && (
        <ModalShell
          isOpen={isCreditMemoModalOpen}
          onClose={() => setIsCreditMemoModalOpen(false)}
          title={
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Percent className="w-5 h-5 text-purple-600" />
              Issue Credit Memo Adjustment
            </h3>
          }
        >
          <form onSubmit={handleCreditMemoSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Credit Amount (USD) *</label>
              <input
                type="number"
                step="0.01"
                required
                value={creditMemoAmount}
                onChange={(e) => setCreditMemoAmount(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Adjustment Reason *</label>
              <input
                type="text"
                required
                value={creditMemoReason}
                onChange={(e) => setCreditMemoReason(e.target.value)}
                placeholder="e.g. Volume discount adjustment"
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
              <button type="button" onClick={() => setIsCreditMemoModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                Cancel
              </button>
              <button
                type="submit"
                disabled={creditMemoMutation.isPending}
                className="flex items-center gap-2 bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
              >
                {creditMemoMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Issue Credit Memo
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* Send Email Modal */}
      {isSendEmailModalOpen && (
        <ModalShell
          isOpen={isSendEmailModalOpen}
          onClose={() => setIsSendEmailModalOpen(false)}
          title={
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Send className="w-5 h-5 text-blue-600" />
              Email Invoice & Payment Link
            </h3>
          }
        >
          <form onSubmit={handleSendEmailSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Recipient Email Address *</label>
              <input
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
