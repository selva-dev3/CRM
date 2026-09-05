'use client';

import { Input } from "@/components/ui/input";

import { getErrorMessage } from '@/lib/utils';
import React, { useEffect, useRef, useState } from 'react';
import { useHasPermission } from '@/hooks/use-has-permission';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  FileCode,
  Send,
  CheckCircle2,
  Download,
  Receipt,
  AlertCircle,
  X,
  Loader2,
  Trash2,
  History
} from 'lucide-react';
import { ActionMenu } from '@/components/common/action-menu';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ModalShell } from '@/components/common/modal-shell';
import {
  useQuoteQuery,
  useQuotePdfQuery,
  useQuoteRevisionsQuery,
  useSendQuoteEmailMutation,
  useDeleteQuoteMutation
} from '@/lib/api/quotes';

function maskEmail(email?: string | null): string {
  if (!email) return 'Not available';
  const [local, domain] = email.split('@');
  if (!domain || local.length < 3) return email;
  return `${local.slice(0, 2)}${'*'.repeat(Math.max(3, local.length - 2))}@${domain}`;
}

function maskIdentifier(value?: string | null): string {
  if (!value) return 'Not available';
  if (value.length <= 8) return '••••••••';
  return `${value.slice(0, 4)}…${value.slice(-4)}`;
}

export default function QuoteDetailPage() {
  const params = useParams();
  const router = useRouter();
  const quoteId = (params?.id as string) || '';
  const { hasPermission } = useHasPermission();

  // Queries
  const { data: quote, isLoading, isError } = useQuoteQuery(quoteId, {
    refetchInterval: query => ['Pending', 'Processing'].includes(query.state.data?.delivery_status || '') ? 5000 : false,
  });
  const { data: pdfData } = useQuotePdfQuery(quoteId, { enabled: !!quote?.pdf_available });
  const { data: revisions = [] } = useQuoteRevisionsQuery(quoteId);

  // Mutations
  const sendEmailMutation = useSendQuoteEmailMutation();
  const deleteMutation = useDeleteQuoteMutation();
  const awaitingDeliverySuccessRef = useRef(false);

  // State
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isSendEmailModalOpen, setIsSendEmailModalOpen] = useState(false);
  const [recipientEmailInput, setRecipientEmailInput] = useState('');

  // Toast / Alert notifications
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (
      awaitingDeliverySuccessRef.current &&
      quote?.delivery_status === 'Sent' &&
      quote.provider_message_id
    ) {
      setSuccessMessage(
        `Quote sent successfully to ${maskEmail(quote.recipient_email)}. Waiting for customer approval.`,
      );
      awaitingDeliverySuccessRef.current = false;
    }
  }, [quote?.delivery_status, quote?.provider_message_id, quote?.recipient_email]);

  const handleSendEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recipientEmailInput.trim() || sendEmailMutation.isPending) return;
    try {
      awaitingDeliverySuccessRef.current = true;
      await sendEmailMutation.mutateAsync({ id: quoteId, recipient_email: recipientEmailInput.trim() });
      setErrorMessage(null);
      setIsSendEmailModalOpen(false);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to send email.'));
    }
  };

  const handleDeleteQuote = async () => {
    try {
      await deleteMutation.mutateAsync(quoteId);
      router.push('/quotes');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to delete quote.'));
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-2 text-slate-500">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
          <span className="text-sm font-medium">Loading quote proposal...</span>
        </div>
      </div>
    );
  }

  if (isError || !quote) {
    return (
      <div className="p-6 max-w-2xl mx-auto space-y-4">
        <Link href="/quotes" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900 font-medium">
          <ArrowLeft className="w-4 h-4" />
          Back to Quotes
        </Link>
        <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 space-y-2">
          <div className="flex items-center gap-2 font-bold text-base">
            <AlertCircle className="w-5 h-5 text-rose-600" />
            Quote Proposal Not Found
          </div>
          <p className="text-sm">The sales quote proposal you requested could not be found or may have been deleted.</p>
        </div>
      </div>
    );
  }

  const s = quote.status || 'Draft';
  const deliveryStatus = quote.delivery_status || 'Not queued';
  const pdfAvailable = quote.pdf_available === true;
  const deliveryMessage =
    deliveryStatus === 'Pending'
      ? 'Email delivery queued'
      : deliveryStatus === 'Processing'
      ? 'Generating PDF and sending email...'
      : deliveryStatus === 'Sent'
      ? 'Email sent successfully'
      : deliveryStatus === 'Delivered'
      ? 'Email delivered to customer'
      : deliveryStatus === 'Failed' || deliveryStatus === 'Bounced'
      ? 'Email delivery failed'
      : deliveryStatus === 'Unknown'
      ? 'Email delivery status could not be confirmed'
      : 'Email delivery has not been queued';
  const pdfMessage = pdfAvailable
    ? 'Available ✓'
    : deliveryStatus === 'Processing'
    ? 'Generating and uploading...'
    : deliveryStatus === 'Pending'
    ? 'Waiting for processing'
    : deliveryStatus === 'Failed' || deliveryStatus === 'Bounced'
    ? 'Not available — delivery failed'
    : deliveryStatus === 'Unknown'
    ? 'Unavailable — reconciliation required'
    : 'Not generated';
  const badgeStyle =
    s === 'Accepted'
      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
      : s === 'Rejected'
      ? 'bg-rose-50 text-rose-700 border-rose-200'
      : s === 'Sent'
      ? 'bg-blue-50 text-blue-700 border-blue-200'
      : 'bg-amber-50 text-amber-700 border-amber-200';

  return (
    <div className="space-y-6 w-full pb-12">
      {/* Navigation & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <Link href="/quotes" className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-indigo-600 transition-colors">
            <ArrowLeft className="w-4 h-4" />
            Back to Quotes & Proposals
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
              <FileCode className="w-6 h-6 text-indigo-600" />
              Quote: {quote.quote_number}
            </h1>
            <span className={`px-3 py-0.5 rounded-full text-xs font-semibold border ${badgeStyle}`}>
              {s === 'Accepted' ? 'Customer Accepted ✓' : s === 'Rejected' ? 'Customer Rejected' : s === 'Sent' ? 'Sent ✓' : s}
            </span>
          </div>
        </div>

        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          {hasPermission('quotes:send') && ['Draft', 'Pending Approval'].includes(s) && (
            <Button
              onClick={() => { setRecipientEmailInput(quote.contact_email || quote.recipient_email || ''); setIsSendEmailModalOpen(true); }}
              disabled={sendEmailMutation.isPending || deliveryStatus === 'Processing'}
              className="w-full gap-2 bg-indigo-600 text-xs font-semibold hover:bg-indigo-700 sm:w-auto"
            >
              <Send className="w-4 h-4" />
              {deliveryStatus === 'Failed' || deliveryStatus === 'Bounced' ? 'Retry Quote Delivery' : 'Send Quote'}
            </Button>
          )}

          {quote.invoice_id && (
            <Button asChild variant="outline"><Link href={`/invoices/${quote.invoice_id}`}>
              <Receipt className="mr-2 h-4 w-4" />View generated invoice
            </Link></Button>
          )}

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
            actions={[
              {
                label: 'Delete quote',
                icon: <Trash2 className="w-4 h-4" />,
                variant: 'destructive',
                onSelect: () => setIsDeleteModalOpen(true),
              },
            ]}
          />
        </div>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900">Customer Email Delivery</h2>
          <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-700">
            Quote: {s}
          </span>
        </div>
        <div className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Recipient</p>
            <p className="mt-1 font-semibold text-slate-900">{maskEmail(quote.recipient_email || quote.contact_email)}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Email status</p>
            <p className={`mt-1 font-semibold ${deliveryStatus === 'Failed' || deliveryStatus === 'Bounced' ? 'text-rose-700' : deliveryStatus === 'Delivered' ? 'text-emerald-700' : 'text-slate-900'}`}>
              {deliveryMessage}
            </p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">PDF</p>
            <p className={`mt-1 font-semibold ${pdfAvailable ? 'text-emerald-700' : 'text-slate-900'}`}>{pdfMessage}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Sent at</p>
            <p className="mt-1 font-semibold text-slate-900">{quote.sent_at ? new Date(quote.sent_at).toLocaleString() : 'Not sent'}</p>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-slate-100 pt-4 text-xs text-slate-500">
          <span>Delivery ID: {maskIdentifier(quote.delivery_id)}</span>
          {quote.provider_message_id && <span>Provider message: {maskIdentifier(quote.provider_message_id)}</span>}
          {deliveryStatus === 'Sent' && <span>Email provider accepted the request; inbox delivery is not confirmed.</span>}
        </div>
        {deliveryStatus === 'Failed' && (
          <p role="alert" className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs font-medium text-rose-800">
            PDF generation or email delivery failed. Retry is available when the existing delivery rules allow it.
          </p>
        )}
        {deliveryStatus === 'Unknown' && (
          <p role="alert" className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs font-medium text-amber-900">
            Email delivery status could not be confirmed. Do not resend until provider reconciliation completes.
          </p>
        )}
      </section>
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
        {/* Left Column: Quote Line Items & Totals */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-6">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3">
              Quote Line Items & Breakdown
            </h3>

            <div className="overflow-x-auto">
              <Table className="w-full text-left text-xs text-slate-700">
                <TableHeader className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  <TableRow>
                    <TableHead className="p-3">ITEM DESCRIPTION</TableHead>
                    <TableHead className="p-3 text-center">QTY</TableHead>
                    <TableHead className="p-3 text-right">UNIT PRICE</TableHead>
                    <TableHead className="p-3 text-right">DISCOUNT</TableHead>
                    <TableHead className="p-3 text-right">TAX</TableHead>
                    <TableHead className="p-3 text-right">SUBTOTAL</TableHead>
                    <TableHead className="p-3 text-right">TOTAL</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody className="divide-y divide-slate-100">
                  {quote.items && quote.items.length > 0 ? (
                    quote.items.map((item, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="p-3 font-semibold text-slate-900">{item.product_name || item.name}</TableCell>
                        <TableCell className="p-3 text-center font-mono">{item.quantity}</TableCell>
                        <TableCell className="p-3 text-right">${item.unit_price.toLocaleString()}</TableCell>
                        <TableCell className="p-3 text-right">{item.discount_percent ?? 0}%</TableCell>
                        <TableCell className="p-3 text-right">{item.tax_percent ?? 0}%</TableCell>
                        <TableCell className="p-3 text-right">{(item.subtotal ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</TableCell>
                        <TableCell className="p-3 text-right font-bold text-slate-900">${item.total.toLocaleString()}</TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow><TableCell colSpan={7} className="p-6 text-center text-slate-500">No persisted quote items are available.</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </div>

            <div className="flex justify-end pt-4 border-t border-slate-100">
              <div className="w-64 space-y-2 text-xs">
                <div className="flex justify-between text-slate-600 font-medium">
                  <span>Subtotal:</span>
                  <span>{quote.currency || 'USD'} {quote.items?.reduce((sum, item) => sum + (item.subtotal ?? item.total ?? 0), 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="flex justify-between text-slate-600 font-medium">
                  <span>Tax (0%):</span>
                  <span>{quote.currency || 'USD'} {(quote.items?.reduce((sum, item) => sum + (item.tax_total ?? 0), 0) || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
                <div className="flex justify-between text-slate-900 font-extrabold text-sm border-t border-slate-200 pt-2">
                  <span>Grand Total:</span>
                  <span className="text-emerald-600">{quote.currency || 'USD'} {quote.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Historical Revisions Drawer */}
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3 flex items-center gap-2">
              <History className="w-4 h-4 text-amber-500" />
              Proposal Revision History
            </h3>

            <div className="space-y-3">
              {revisions.length === 0 ? (
                <p className="text-xs text-slate-400 italic">No historical revisions found.</p>
              ) : (
                revisions.map((rev) => (
                  <div key={rev.id} className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
                    <div className="flex justify-between items-center text-xs font-bold text-slate-900">
                      <span>{rev.quote_number}</span>
                      <span className="px-2 py-0.5 bg-amber-100 text-amber-800 rounded text-[10px] font-mono">{rev.version}</span>
                    </div>
                    <div className="flex justify-between items-center text-[11px] text-slate-500">
                      <span>Amount: ${rev.total_amount.toLocaleString()}</span>
                      <span>{rev.created_at}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      <section className="grid grid-cols-1 gap-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:grid-cols-2 lg:grid-cols-4">
        <div><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Company</p><p className="mt-1 text-sm font-semibold text-slate-900">{quote.company_name || 'Not available'}</p></div>
        <div><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Contact</p><p className="mt-1 text-sm font-semibold text-slate-900">{quote.contact_name || 'Not available'}</p><p className="text-xs text-slate-500">{quote.contact_email || 'Email not available'}</p></div>
        <div><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Currency / expiry</p><p className="mt-1 text-sm font-semibold text-slate-900">{quote.currency || 'Not available'}</p><p className="text-xs text-slate-500">Expires {quote.expires_at ? quote.expires_at.substring(0, 10) : 'not set'}</p></div>
        <div><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Commercial terms</p><p className="mt-1 text-sm font-semibold text-slate-900">{quote.payment_terms || 'Not specified'}</p><p className="text-xs text-slate-500">Due {quote.due_date ? quote.due_date.substring(0, 10) : 'not set'}</p></div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-900">Customer Approval</h2>
        <p className="mt-2 text-sm font-semibold text-slate-900">
          {s === 'Accepted'
            ? 'Customer accepted the quote.'
            : s === 'Rejected'
            ? 'Customer rejected the quote.'
            : s === 'Sent'
            ? 'Waiting for customer approval.'
            : 'Quote is ready to send to the customer.'}
        </p>
        {quote.accepted_at && <p className="mt-1 text-xs text-slate-500">Accepted at {new Date(quote.accepted_at).toLocaleString()}</p>}
        {quote.invoice_id && <p className="mt-2 text-xs font-medium text-emerald-700">Invoice {quote.invoice_number || quote.invoice_id} created · {quote.invoice_status || 'Pending'}</p>}
      </section>

      {/* Send Email Modal */}
      {isSendEmailModalOpen && (
        <ModalShell
          isOpen={isSendEmailModalOpen}
          onClose={() => setIsSendEmailModalOpen(false)}
          title={
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Send className="w-5 h-5 text-blue-600" />
              {deliveryStatus === 'Failed' || deliveryStatus === 'Bounced' ? 'Retry Quote Delivery' : 'Send Quote to Customer'}
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
                {deliveryStatus === 'Failed' || deliveryStatus === 'Bounced' ? 'Retry Delivery' : 'Send Quote'}
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* Delete Confirm Modal */}
      {isDeleteModalOpen && (
        <ConfirmModal
          isOpen={isDeleteModalOpen}
          title="Delete Quote Proposal"
          description={`Are you sure you want to delete proposal "${quote.quote_number}"?`}
          confirmText="Delete Quote"
          variant="danger"
          onConfirm={handleDeleteQuote}
          onClose={() => setIsDeleteModalOpen(false)}
        />
      )}
    </div>
  );
}
