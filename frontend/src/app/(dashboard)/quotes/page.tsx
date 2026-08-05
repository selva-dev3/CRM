'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  FileCode,
  Calendar,
  DollarSign,
  Building,
  Plus,
  Search,
  Download,
  Upload,
  Trash2,
  Edit,
  Send,
  CheckCircle2,
  XCircle,
  FileCheck,
  FileText,
  AlertCircle,
  X,
  Loader2,
  TrendingUp,
  Receipt
} from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/shared/data-table';
import { ConfirmModal } from '@/components/shared/confirm-modal';
import {
  useQuotesQuery,
  useCreateQuoteMutation,
  useUpdateQuoteMutation,
  useDeleteQuoteMutation,
  useBulkDeleteQuotesMutation,
  useSendQuoteEmailMutation,
  useAcceptQuoteMutation,
  useRejectQuoteMutation,
  useConvertQuoteToInvoiceMutation,
  useImportQuotesCsvMutation,
  exportQuotesCsvApi,
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
  const [totalAmount, setTotalAmount] = useState('15000');
  const [status, setStatus] = useState('Draft');

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
  const acceptQuoteMutation = useAcceptQuoteMutation();
  const convertInvoiceMutation = useConvertQuoteToInvoiceMutation();
  const importCsvMutation = useImportQuotesCsvMutation();

  const resetForm = () => {
    setQuoteNumber('');
    setTotalAmount('15000');
    setStatus('Draft');
    setEditingQuote(null);
  };

  const handleOpenCreateModal = () => {
    resetForm();
    setIsQuoteModalOpen(true);
  };

  const handleOpenEditModal = (q: QuoteItem) => {
    setEditingQuote(q);
    setQuoteNumber(q.quote_number);
    setTotalAmount(String(q.total_amount || 0));
    setStatus(q.status || 'Draft');
    setIsQuoteModalOpen(true);
  };

  const handleSaveQuoteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload: QuoteCreatePayload = {
      quote_number: quoteNumber.trim() || `QUO-2026-${Math.floor(1000 + Math.random() * 9000)}`,
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
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to save quote proposal.');
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
      setSuccessMessage(`Quote proposal email sent to ${recipientEmailInput.trim()}.`);
      setIsSendEmailModalOpen(false);
      setSendModalQuote(null);
      setRecipientEmailInput('');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to send quote email.');
    }
  };

  const handleAcceptQuote = async (q: QuoteItem) => {
    try {
      await acceptQuoteMutation.mutateAsync(q.id);
      setSuccessMessage(`Quote "${q.quote_number}" marked as Accepted.`);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to mark quote as accepted.');
    }
  };

  const handleConvertToInvoice = async (q: QuoteItem) => {
    try {
      const res = await convertInvoiceMutation.mutateAsync(q.id);
      setSuccessMessage(`Quote "${q.quote_number}" converted into Invoice #${res.invoice_number}!`);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to convert quote into invoice.');
    }
  };

  const handleExportCsv = async () => {
    try {
      const res = await exportQuotesCsvApi();
      setSuccessMessage('Quotes list exported. Download started.');
      window.open(res.download_url, '_blank');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to export quotes CSV.');
    }
  };

  const handleImportCsv = async () => {
    try {
      const res = await importCsvMutation.mutateAsync();
      setSuccessMessage(res.message || 'Quotes CSV import processing completed.');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to import quotes CSV.');
    }
  };

  const handleDeleteQuote = async () => {
    if (!quoteToDelete) return;
    try {
      await deleteQuoteMutation.mutateAsync(quoteToDelete.id);
      setSuccessMessage('Quote deleted successfully.');
      setQuoteToDelete(null);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete quote.');
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    try {
      const res = await bulkDeleteMutation.mutateAsync(Array.from(selectedIds));
      setSuccessMessage(`${res.affected_count || selectedIds.size} quote(s) deleted.`);
      setSelectedIds(new Set());
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete selected quotes.');
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
          <span>{item.created_at ? item.created_at.substring(0, 10) : '2026-08-05'}</span>
        </div>
      ),
    },
    {
      id: 'actions',
      header: 'ACTIONS',
      cell: (item) => (
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => {
              setSendModalQuote(item);
              setRecipientEmailInput('client@company.com');
              setIsSendEmailModalOpen(true);
            }}
            title="Send Proposal Email"
            className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-md transition-colors cursor-pointer"
          >
            <Send className="w-4 h-4" />
          </button>

          {item.status !== 'Accepted' ? (
            <button
              onClick={() => handleAcceptQuote(item)}
              title="Mark as Accepted"
              className="p-1.5 text-emerald-600 hover:bg-emerald-50 rounded-md transition-colors cursor-pointer"
            >
              <CheckCircle2 className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={() => handleConvertToInvoice(item)}
              title="Convert to Invoice"
              className="p-1.5 text-purple-600 hover:bg-purple-50 rounded-md transition-colors cursor-pointer flex items-center gap-1 text-xs font-semibold"
            >
              <Receipt className="w-4 h-4" />
              Invoice
            </button>
          )}

          <button
            onClick={() => handleOpenEditModal(item)}
            title="Edit Quote"
            className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-slate-100 rounded-md transition-colors cursor-pointer"
          >
            <Edit className="w-4 h-4" />
          </button>

          <button
            onClick={() => setQuoteToDelete(item)}
            title="Delete Quote"
            className="p-1.5 text-slate-500 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors cursor-pointer"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
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

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <FileCode className="w-7 h-7 text-indigo-600" />
            Quotes & Sales Proposals
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">Create, send, track client approvals, generate PDF reports & convert quotes directly to invoices</p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={handleExportCsv}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer"
          >
            <Download className="w-4 h-4 text-slate-600" />
            Export CSV
          </button>

          <button
            onClick={handleImportCsv}
            disabled={importCsvMutation.isPending}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer disabled:opacity-50"
          >
            {importCsvMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4 text-indigo-600" />}
            Import CSV
          </button>

          <button
            onClick={handleOpenCreateModal}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-semibold text-sm transition-colors shadow-sm cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            Create Quote
          </button>
        </div>
      </div>

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">TOTAL QUOTES</p>
            <h3 className="text-2xl font-bold text-slate-900 mt-1">{quotes.length}</h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600">
            <FileCode className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">ACCEPTED QUOTES</p>
            <h3 className="text-2xl font-bold text-emerald-600 mt-1">
              {quotes.filter((q) => q.status === 'Accepted').length}
            </h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-600">
            <FileCheck className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">SENT / PENDING</p>
            <h3 className="text-2xl font-bold text-blue-600 mt-1">
              {quotes.filter((q) => q.status === 'Sent').length}
            </h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-blue-50 flex items-center justify-center text-blue-600">
            <Send className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">CONVERSION RATE</p>
            <h3 className="text-2xl font-bold text-purple-600 mt-1">78%</h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-purple-50 flex items-center justify-center text-purple-600">
            <TrendingUp className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Main Data Table */}
      <DataTable<QuoteItem>
        columns={columns}
        data={quotes}
        getRowKey={(item) => item.id}
        onRowClick={(item) => router.push(`/quotes/${item.id}`)}
        emptyTitle="No sales quotes found"
        emptyDescription="Create a new quote proposal or adjust your status filter."
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search quote number or client..."
        toolbarActions={
          <div className="flex items-center gap-3">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-700 outline-none shadow-xs"
            >
              <option value="">All Statuses</option>
              <option value="Draft">Draft</option>
              <option value="Sent">Sent</option>
              <option value="Accepted">Accepted</option>
              <option value="Rejected">Rejected</option>
            </select>

            {selectedIds.size > 0 && (
              <div className="flex items-center gap-2 bg-indigo-50 px-3 py-1 rounded-lg border border-indigo-200">
                <span className="text-xs font-semibold text-indigo-700">{selectedIds.size} selected</span>
                <button
                  onClick={handleBulkDelete}
                  className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded text-xs font-semibold cursor-pointer"
                >
                  Bulk Delete
                </button>
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
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-5">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <FileCode className="w-5 h-5 text-indigo-600" />
                {editingQuote ? 'Edit Sales Quote' : 'Create Sales Quote'}
              </h2>
              <button onClick={() => setIsQuoteModalOpen(false)} className="text-slate-400 hover:text-slate-600 p-1 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveQuoteSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                  Quote Reference Number
                </label>
                <input
                  type="text"
                  value={quoteNumber}
                  onChange={(e) => setQuoteNumber(e.target.value)}
                  placeholder="e.g. Q-2026-0801"
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none font-mono"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                    Total Amount (USD) *
                  </label>
                  <input
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
                  <select
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                  >
                    <option value="Draft">Draft</option>
                    <option value="Sent">Sent</option>
                    <option value="Accepted">Accepted</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
                <button type="button" onClick={() => setIsQuoteModalOpen(false)} className="px-4 py-2 text-sm font-medium text-slate-600">
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createQuoteMutation.isPending || updateQuoteMutation.isPending}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-lg font-medium text-sm cursor-pointer shadow-sm disabled:opacity-50"
                >
                  {(createQuoteMutation.isPending || updateQuoteMutation.isPending) && (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  )}
                  {editingQuote ? 'Save Changes' : 'Create Quote'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Send Email Modal */}
      {isSendEmailModalOpen && sendModalQuote && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Send className="w-5 h-5 text-blue-600" />
                Send Quote Proposal
              </h3>
              <button onClick={() => setIsSendEmailModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSendEmailSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Recipient Email Address *</label>
                <input
                  type="email"
                  required
                  value={recipientEmailInput}
                  onChange={(e) => setRecipientEmailInput(e.target.value)}
                  placeholder="client@company.com"
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
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
          </div>
        </div>
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
