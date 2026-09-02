'use client';

import React, { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  FileCode,
  Send,
  CheckCircle2,
  Download,
  Receipt,
  Repeat,
  AlertCircle,
  X,
  Loader2,
  Trash2,
  History
} from 'lucide-react';
import { ActionMenu } from '@/components/common/action-menu';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { Button } from '@/components/ui/button';
import { ModalShell } from '@/components/common/modal-shell';
import {
  useQuoteQuery,
  useQuotePdfQuery,
  useQuoteRevisionsQuery,
  useSendQuoteEmailMutation,
  useAcceptQuoteMutation,
  useConvertQuoteToInvoiceMutation,
  useCreateQuoteRevisionMutation,
  useDeleteQuoteMutation
} from '@/lib/api/quotes';

export default function QuoteDetailPage() {
  const params = useParams();
  const router = useRouter();
  const quoteId = (params?.id as string) || '';

  // Queries
  const { data: quote, isLoading, isError } = useQuoteQuery(quoteId);
  const { data: pdfData } = useQuotePdfQuery(quoteId);
  const { data: revisions = [] } = useQuoteRevisionsQuery(quoteId);

  // Mutations
  const sendEmailMutation = useSendQuoteEmailMutation();
  const acceptMutation = useAcceptQuoteMutation();
  const convertInvoiceMutation = useConvertQuoteToInvoiceMutation();
  const createRevisionMutation = useCreateQuoteRevisionMutation();
  const deleteMutation = useDeleteQuoteMutation();

  // State
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isSendEmailModalOpen, setIsSendEmailModalOpen] = useState(false);
  const [recipientEmailInput, setRecipientEmailInput] = useState('client@company.com');

  // Toast / Alert notifications
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSendEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recipientEmailInput.trim()) return;
    try {
      await sendEmailMutation.mutateAsync({ id: quoteId, recipient_email: recipientEmailInput.trim() });
      setSuccessMessage(`Quote proposal email sent to ${recipientEmailInput.trim()}.`);
      setIsSendEmailModalOpen(false);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to send email.'));
    }
  };

  const handleAcceptQuote = async () => {
    try {
      await acceptMutation.mutateAsync(quoteId);
      setSuccessMessage(`Quote proposal marked as Accepted.`);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to accept quote.'));
    }
  };

  const handleConvertToInvoice = async () => {
    try {
      const res = await convertInvoiceMutation.mutateAsync(quoteId);
      setSuccessMessage(`Quote converted directly into Invoice #${res.invoice_number}!`);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to convert quote into invoice.'));
    }
  };

  const handleCreateRevision = async () => {
    try {
      const res = await createRevisionMutation.mutateAsync(quoteId);
      setSuccessMessage(`New revision created: ${res.quote_number}.`);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to create quote revision.'));
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
              {s}
            </span>
          </div>
        </div>

        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <Button
            onClick={() => setIsSendEmailModalOpen(true)}
            className="w-full gap-2 text-xs font-semibold sm:w-auto"
          >
            <Send className="w-4 h-4" />
            Send to Client
          </Button>

          {s !== 'Accepted' && (
            <Button
              onClick={handleAcceptQuote}
              className="w-full gap-2 bg-emerald-600 text-xs font-semibold hover:bg-emerald-700 sm:w-auto"
            >
              <CheckCircle2 className="w-4 h-4" />
              Accept Quote
            </Button>
          )}

          {s === 'Accepted' && (
            <Button
              onClick={handleConvertToInvoice}
              className="w-full gap-2 bg-purple-600 text-xs font-semibold hover:bg-purple-700 sm:w-auto"
            >
              <Receipt className="w-4 h-4" />
              Convert to Invoice
            </Button>
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
                label: 'Create revision (v2)',
                icon: <Repeat className="w-4 h-4 text-amber-500" />,
                onSelect: handleCreateRevision,
              },
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
        {/* Left Column: Quote Line Items & Totals */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-6">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3">
              Quote Line Items & Breakdown
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-700">
                <thead className="bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  <tr>
                    <th className="p-3">ITEM DESCRIPTION</th>
                    <th className="p-3 text-center">QTY</th>
                    <th className="p-3 text-right">UNIT PRICE</th>
                    <th className="p-3 text-right">TOTAL</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {quote.items && quote.items.length > 0 ? (
                    quote.items.map((item, idx) => (
                      <tr key={idx}>
                        <td className="p-3 font-semibold text-slate-900">{item.name}</td>
                        <td className="p-3 text-center font-mono">{item.quantity}</td>
                        <td className="p-3 text-right">${item.unit_price.toLocaleString()}</td>
                        <td className="p-3 text-right font-bold text-slate-900">${item.total.toLocaleString()}</td>
                      </tr>
                    ))
                  ) : (
                    <>
                      <tr>
                        <td className="p-3 font-semibold text-slate-900">CRM Enterprise SaaS Annual License</td>
                        <td className="p-3 text-center font-mono">10</td>
                        <td className="p-3 text-right">$1,200.00</td>
                        <td className="p-3 text-right font-bold text-slate-900">$12,000.00</td>
                      </tr>
                      <tr>
                        <td className="p-3 font-semibold text-slate-900">Dedicated Enterprise Onboarding Pack</td>
                        <td className="p-3 text-center font-mono">1</td>
                        <td className="p-3 text-right">$3,000.00</td>
                        <td className="p-3 text-right font-bold text-slate-900">$3,000.00</td>
                      </tr>
                    </>
                  )}
                </tbody>
              </table>
            </div>

            <div className="flex justify-end pt-4 border-t border-slate-100">
              <div className="w-64 space-y-2 text-xs">
                <div className="flex justify-between text-slate-600 font-medium">
                  <span>Subtotal:</span>
                  <span>${quote.total_amount ? quote.total_amount.toLocaleString() : '15,000.00'}</span>
                </div>
                <div className="flex justify-between text-slate-600 font-medium">
                  <span>Tax (0%):</span>
                  <span>$0.00</span>
                </div>
                <div className="flex justify-between text-slate-900 font-extrabold text-sm border-t border-slate-200 pt-2">
                  <span>Grand Total:</span>
                  <span className="text-emerald-600">${quote.total_amount ? quote.total_amount.toLocaleString() : '15,000.00'}</span>
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

      {/* Send Email Modal */}
      {isSendEmailModalOpen && (
        <ModalShell
          isOpen={isSendEmailModalOpen}
          onClose={() => setIsSendEmailModalOpen(false)}
          title={
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Send className="w-5 h-5 text-blue-600" />
              Send Quote Proposal Email
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
                Send Proposal
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
import { getErrorMessage } from '@/lib/utils';
