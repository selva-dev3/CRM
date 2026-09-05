'use client';

import { Input } from "@/components/ui/input";

import { ResponsiveSelect } from '@/components/common/responsive-select';

import { ActionMenu } from '@/components/common/action-menu';
import { getErrorMessage } from '@/lib/utils';
import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  FileCode,
  Calendar,
  DollarSign,
  Trash2,
  Edit,
  Send,
  CheckCircle2,
  AlertCircle,
  X,
  Loader2,
} from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { ModalShell } from '@/components/common/modal-shell';
import { PermissionGate } from '@/components/common/permission-gate';
import { PERMISSIONS } from '@/lib/permissions';
import { useDealsQuery } from '@/lib/api/deals';
import {
  useQuotesQuery,
  useCreateQuoteMutation,
  useUpdateQuoteMutation,
  useDeleteQuoteMutation,
  useBulkDeleteQuotesMutation,
  useSendQuoteEmailMutation,
  QuoteItem,
  QuoteCreatePayload
} from '@/lib/api/quotes';

export default function QuotesPage() {
  const router = useRouter();
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [page, setPage] = useState(1);
  const limit = 15;

  // Selected quotes for bulk action
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Modal states
  const [isQuoteModalOpen, setIsQuoteModalOpen] = useState(false);
  const [isSendEmailModalOpen, setIsSendEmailModalOpen] = useState(false);
  const [sendModalQuote, setSendModalQuote] = useState<QuoteItem | null>(null);
  const [recipientEmailInput, setRecipientEmailInput] = useState('');
  const [editingQuote, setEditingQuote] = useState<QuoteItem | null>(null);
  const [quoteToDelete, setQuoteToDelete] = useState<QuoteItem | null>(null);

  // Form states
  const [quoteNumber, setQuoteNumber] = useState('');
  const [totalAmount, setTotalAmount] = useState('0');
  const [status, setStatus] = useState('Draft');
  const [dealId, setDealId] = useState('');

  // Toast / Alert notifications
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Debounce search
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
      setPage(1);
    }, 250);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  // Queries
  const { data: deals = [], isLoading: isDealsLoading, isError: isDealsError } = useDealsQuery(1, 100);

  const { data: quotes = [], isLoading: isQuotesLoading } = useQuotesQuery({
    page,
    limit,
    status: statusFilter || undefined,
    search: debouncedSearchTerm || undefined,
  });

  // Mutations
  const createQuoteMutation = useCreateQuoteMutation();
  const updateQuoteMutation = useUpdateQuoteMutation();
  const deleteQuoteMutation = useDeleteQuoteMutation();
  const bulkDeleteMutation = useBulkDeleteQuotesMutation();
  const sendEmailMutation = useSendQuoteEmailMutation();

  const resetForm = () => {
    setQuoteNumber('');
    setTotalAmount('0');
    setStatus('Draft');
    setDealId('');
    setEditingQuote(null);
  };

  const handleOpenEditModal = (q: QuoteItem) => {
    setEditingQuote(q);
    setQuoteNumber(q.quote_number);
    setTotalAmount(String(q.total_amount || 0));
    setStatus(q.status || 'Draft');
    setDealId(q.deal_id || '');
    setIsQuoteModalOpen(true);
  };

  const handleSaveQuoteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingQuote && !dealId) {
      setErrorMessage('Select a deal before creating the quote.');
      return;
    }
    if (editingQuote && !dealId) {
      setErrorMessage('This quote is missing its associated deal. Select a deal before saving.');
      return;
    }
    const payload: QuoteCreatePayload = {
      deal_id: dealId,
      quote_number: quoteNumber.trim(),
      total_amount: parseFloat(totalAmount || '0'),
      status: status,
    };

    try {
      if (editingQuote) {
        await updateQuoteMutation.mutateAsync({ id: editingQuote.id, payload });
        setSuccessMessage(`Quote proposal "${editingQuote.quote_number}" updated.`);
      } else {
        await createQuoteMutation.mutateAsync(payload);
        setSuccessMessage('New quote proposal created successfully.');
      }
      setIsQuoteModalOpen(false);
      resetForm();
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to save quote proposal.'));
    }
  };

  const handleSendEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sendModalQuote || !recipientEmailInput.trim()) return;
    try {
      await sendEmailMutation.mutateAsync({
        id: sendModalQuote.id,
        recipient_email: recipientEmailInput.trim(),
      });
      setSuccessMessage(`Quote proposal queued for delivery to ${recipientEmailInput.trim()}.`);
      setIsSendEmailModalOpen(false);
      setSendModalQuote(null);
      setRecipientEmailInput('');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to send quote email.'));
    }
  };

  const handleDeleteQuote = async () => {
    if (!quoteToDelete) return;
    try {
      await deleteQuoteMutation.mutateAsync(quoteToDelete.id);
      setSuccessMessage('Quote deleted successfully.');
      setQuoteToDelete(null);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to delete quote.'));
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    try {
      const res = await bulkDeleteMutation.mutateAsync(Array.from(selectedIds));
      setSuccessMessage(`${res.affected_count || selectedIds.size} quote(s) deleted.`);
      setSelectedIds(new Set());
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to delete selected quotes.'));
    }
  };

  // Columns definition
  const columns: DataTableColumn<QuoteItem>[] = [
    {
      id: 'quote_number',
      header: 'QUOTE REF',
      cell: (item) => (
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 font-bold shrink-0">
            <FileCode className="w-4 h-4" />
          </div>
          <div>
            <div
              onClick={(e) => {
                e.stopPropagation();
                router.push(`/quotes/${item.id}`);
              }}
              className="font-bold text-slate-900 hover:text-indigo-600 cursor-pointer transition-colors text-xs"
            >
              {item.quote_number}
            </div>
            <div className="text-[11px] text-slate-400 font-mono">Client: {item.client || 'Enterprise Client'}</div>
          </div>
        </div>
      ),
    },
    {
      id: 'total_amount',
      header: 'TOTAL VALUE (USD)',
      cell: (item) => (
        <div className="flex items-center gap-1 text-slate-900 font-bold text-xs">
          <DollarSign className="w-3.5 h-3.5 text-emerald-600" />
          <span>{item.total_amount ? item.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2 }) : '0.00'}</span>
        </div>
      ),
    },
    {
      id: 'status',
      header: 'STATUS',
      cell: (item) => {
        const s = item.status || 'Draft';
        const badgeStyle =
          s === 'Accepted'
            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
            : s === 'Rejected'
            ? 'bg-rose-50 text-rose-700 border-rose-200'
            : s === 'Sent'
            ? 'bg-blue-50 text-blue-700 border-blue-200'
            : 'bg-amber-50 text-amber-700 border-amber-200';
        return (
          <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${badgeStyle}`}>
            {s}
          </span>
        );
      },
    },
    {
      id: 'created_at',
      header: 'ISSUED DATE',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-medium">
          <Calendar className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.created_at ? item.created_at.substring(0, 10) : '—'}</span>
        </div>
      ),
    },
    {
      id: 'actions',
      header: 'ACTIONS',
      cell: (item) => (
        <ActionMenu
          iconOnly
          label="Open quote actions"
          onTriggerClick={(event) => event.stopPropagation()}
          actions={[
            ...(item.status === 'Approved' && item.delivery_status === 'Failed' ? [{ label: 'Retry quote delivery', permission: PERMISSIONS.QUOTES.SEND, icon: <Send className="w-4 h-4 text-blue-600" />, onSelect: () => { setSendModalQuote(item); setRecipientEmailInput(item.recipient_email || ''); setIsSendEmailModalOpen(true); } }] : []),
            { label: 'Edit quote', permission: PERMISSIONS.QUOTES.UPDATE, icon: <Edit className="w-4 h-4 text-indigo-600" />, onSelect: () => handleOpenEditModal(item) },
            { label: 'Delete quote', permission: PERMISSIONS.QUOTES.DELETE, icon: <Trash2 className="w-4 h-4" />, variant: 'destructive', onSelect: () => setQuoteToDelete(item) },
          ]}
        />
      ),
    },
  ];

  return (
    <div className="space-y-6 w-full pb-12">
      {/* Toast Feedback */}
      {successMessage && (
        <div className="flex items-center justify-between p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl shadow-sm">
          <div className="flex items-center gap-2 text-sm font-medium">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            <span className="truncate max-w-2xl">{successMessage}</span>
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

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <FileCode className="w-7 h-7 text-indigo-600" />
            Quotes & Sales Proposals
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">Quotes are created from won deals; customer acceptance creates invoices automatically.</p>
        </div>

        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
        </div>
      </div>



      {/* Main Data Table */}
      <DataTable<QuoteItem>
        columns={columns}
        data={quotes}
        getRowKey={(item) => item.id}
        onRowClick={(item) => router.push(`/quotes/${item.id}`)}
        emptyTitle="No sales quotes found"
        emptyDescription="Quotes are created automatically when deals are marked won. Try adjusting your status filter."
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search quote number or client..."
        toolbarActions={
          <div className="flex items-center gap-3">
            <ResponsiveSelect
              value={statusFilter}
              onValueChange={setStatusFilter}
              className="bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-700 outline-none shadow-xs"
            >
              <option value="">All Statuses</option>
              <option value="Draft">Draft</option>
              <option value="Sent">Sent</option>
              <option value="Accepted">Accepted</option>
              <option value="Rejected">Rejected</option>
            </ResponsiveSelect>

            {selectedIds.size > 0 && (
              <div className="flex w-full flex-wrap items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1 sm:w-auto">
                <span className="text-xs font-semibold text-indigo-700">{selectedIds.size} selected</span>
                <PermissionGate permission={PERMISSIONS.QUOTES.DELETE}>
                  <button
                    onClick={handleBulkDelete}
                    className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded text-xs font-semibold cursor-pointer"
                  >
                    Bulk Delete
                  </button>
                </PermissionGate>
              </div>
            )}
          </div>
        }
        isLoading={isQuotesLoading}
        pagination={{
          pageIndex: page - 1,
          pageCount: quotes.length >= limit ? page + 1 : page,
          onPageChange: (p) => setPage(p + 1),
          totalRecords: (page - 1) * limit + quotes.length,
        }}
      />

      {/* Create / Edit Quote Modal */}
      {isQuoteModalOpen && (
        <ModalShell
          isOpen={isQuoteModalOpen}
          onClose={() => setIsQuoteModalOpen(false)}
          size="lg"
          title={
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <FileCode className="w-5 h-5 text-indigo-600" />
              {editingQuote ? 'Edit Sales Quote' : 'Create Sales Quote'}
            </h2>
          }
        >
          <form onSubmit={handleSaveQuoteSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                Quote Reference Number
              </label>
              <Input
                type="text"
                value={quoteNumber}
                onChange={(e) => setQuoteNumber(e.target.value)}
                placeholder="e.g. Q-2026-0801"
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none font-mono"
              />
            </div>

            <div>
              <label htmlFor="quote-deal" className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                Deal *
              </label>
              {isDealsLoading ? (
                <div className="flex items-center gap-2 rounded-lg border border-slate-300 bg-slate-50 px-3.5 py-2 text-sm text-slate-500">
                  <Loader2 className="h-4 w-4 animate-spin" /> Loading deals...
                </div>
              ) : isDealsError ? (
                <p className="rounded-lg border border-rose-200 bg-rose-50 px-3.5 py-2 text-sm text-rose-700">
                  Deals could not be loaded. Close and try again.
                </p>
              ) : deals.length === 0 ? (
                <p className="rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2 text-sm text-amber-700">
                  No deals are available for quote creation.
                </p>
              ) : (
                <ResponsiveSelect
                  id="quote-deal"
                  required
                  value={dealId}
                  onValueChange={setDealId}
                  className="w-full min-w-0 bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                >
                  <option value="">Select a deal</option>
                  {deals.map((deal) => (
                    <option key={deal.id} value={deal.id}>
                      {deal.title} · {deal.stage} · ${deal.amount.toLocaleString()}
                    </option>
                  ))}
                </ResponsiveSelect>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                  Total Amount (USD) *
                </label>
                <Input
                  type="number"
                  step="0.01"
                  required
                  value={totalAmount}
                  onChange={(e) => setTotalAmount(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                  Initial Status
                </label>
                <ResponsiveSelect
                  value={status}
                  onValueChange={setStatus}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                >
                  <option value="Draft">Draft</option>
                  <option value="Pending Approval">Pending Approval</option>
                </ResponsiveSelect>
              </div>
            </div>

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-3 pt-3 border-t border-slate-100">
              <button type="button" onClick={() => setIsQuoteModalOpen(false)} className="px-4 py-2 text-sm font-medium text-slate-600">
                Cancel
              </button>
              <button
                type="submit"
                disabled={createQuoteMutation.isPending || updateQuoteMutation.isPending || isDealsLoading || deals.length === 0 || !dealId}
                className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-lg font-medium text-sm cursor-pointer shadow-sm disabled:opacity-50"
              >
                {(createQuoteMutation.isPending || updateQuoteMutation.isPending) && (
                  <Loader2 className="w-4 h-4 animate-spin" />
                )}
                {editingQuote ? 'Save Changes' : 'Create Quote'}
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* Send Email Modal */}
      {isSendEmailModalOpen && sendModalQuote && (
        <ModalShell
          isOpen={isSendEmailModalOpen}
          onClose={() => setIsSendEmailModalOpen(false)}
          size="md"
          title={
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Send className="w-5 h-5 text-blue-600" />
              Retry Quote Delivery
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
                placeholder="client@company.com"
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-3 pt-2">
              <button type="button" onClick={() => setIsSendEmailModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                Cancel
              </button>
              <button
                type="submit"
                disabled={sendEmailMutation.isPending}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
              >
                {sendEmailMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Retry Delivery
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* Confirm Delete Modal */}
      {quoteToDelete && (
        <ConfirmModal
          isOpen={!!quoteToDelete}
          title="Delete Sales Quote"
          description={`Are you sure you want to delete quote "${quoteToDelete.quote_number}"?`}
          confirmText="Delete Quote"
          variant="danger"
          onConfirm={handleDeleteQuote}
          onClose={() => setQuoteToDelete(null)}
        />
      )}
    </div>
  );
}
