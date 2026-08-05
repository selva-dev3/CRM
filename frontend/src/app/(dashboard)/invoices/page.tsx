'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  FileText,
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
  AlertCircle,
  X,
  Loader2,
  CreditCard,
  BellRing,
  Repeat,
  ShieldCheck,
  Zap,
  Receipt
} from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/shared/data-table';
import { ConfirmModal } from '@/components/shared/confirm-modal';
import {
  useInvoicesQuery,
  useOverdueInvoicesQuery,
  useRecurringInvoicesQuery,
  useCreateInvoiceMutation,
  useUpdateInvoiceMutation,
  useDeleteInvoiceMutation,
  useBulkDeleteInvoicesMutation,
  useBulkRemindInvoicesMutation,
  useSendInvoiceEmailMutation,
  useCreateStripeCheckoutMutation,
  useMarkInvoicePaidMutation,
  useSendPaymentReminderMutation,
  useCreateRecurringInvoiceMutation,
  useImportInvoicesCsvMutation,
  exportInvoicesCsvApi,
  InvoiceItem,
  InvoiceCreatePayload
} from '@/lib/api/invoices';

export default function InvoicesPage() {
  const router = useRouter();
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [page, setPage] = useState(1);
  const limit = 15;

  // Selected invoices for bulk action
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Modal states
  const [isInvoiceModalOpen, setIsInvoiceModalOpen] = useState(false);
  const [isRecurringModalOpen, setIsRecurringModalOpen] = useState(false);
  const [isSendModalOpen, setIsSendModalOpen] = useState(false);
  const [sendModalInvoice, setSendModalInvoice] = useState<InvoiceItem | null>(null);
  const [recipientEmailInput, setRecipientEmailInput] = useState('billing@client.com');
  const [editingInvoice, setEditingInvoice] = useState<InvoiceItem | null>(null);
  const [invoiceToDelete, setInvoiceToDelete] = useState<InvoiceItem | null>(null);

  // Invoice Form states
  const [invoiceNumber, setInvoiceNumber] = useState('');
  const [amount, setAmount] = useState('14500');
  const [dueDate, setDueDate] = useState('2026-09-01');
  const [status, setStatus] = useState('Pending');

  // Recurring Form states
  const [recCustomerId, setRecCustomerId] = useState('Acme Global Corp');
  const [recAmount, setRecAmount] = useState('12000');
  const [recInterval, setRecInterval] = useState('Monthly');

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
  const { data: invoices = [], isLoading: isInvoicesLoading } = useInvoicesQuery({
    page,
    limit,
    status: statusFilter || undefined,
    search: debouncedSearchTerm || undefined,
  });

  const { data: overdueInvoices = [] } = useOverdueInvoicesQuery();
  const { data: recurringSchedules = [] } = useRecurringInvoicesQuery();

  // Mutations
  const createInvoiceMutation = useCreateInvoiceMutation();
  const updateInvoiceMutation = useUpdateInvoiceMutation();
  const deleteInvoiceMutation = useDeleteInvoiceMutation();
  const bulkDeleteMutation = useBulkDeleteInvoicesMutation();
  const bulkRemindMutation = useBulkRemindInvoicesMutation();
  const sendEmailMutation = useSendInvoiceEmailMutation();
  const stripeCheckoutMutation = useCreateStripeCheckoutMutation();
  const markPaidMutation = useMarkInvoicePaidMutation();
  const reminderMutation = useSendPaymentReminderMutation();
  const createRecurringMutation = useCreateRecurringInvoiceMutation();
  const importCsvMutation = useImportInvoicesCsvMutation();

  const resetInvoiceForm = () => {
    setInvoiceNumber('');
    setAmount('14500');
    setDueDate('2026-09-01');
    setStatus('Pending');
    setEditingInvoice(null);
  };

  const handleOpenCreateModal = () => {
    resetInvoiceForm();
    setIsInvoiceModalOpen(true);
  };

  const handleOpenEditModal = (inv: InvoiceItem) => {
    setEditingInvoice(inv);
    setInvoiceNumber(inv.invoice_number);
    setAmount(String(inv.amount || 0));
    setDueDate(inv.due_date ? inv.due_date.substring(0, 10) : '2026-09-01');
    setStatus(inv.status || 'Pending');
    setIsInvoiceModalOpen(true);
  };

  const handleSaveInvoiceSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload: InvoiceCreatePayload = {
      invoice_number: invoiceNumber.trim() || `INV-2026-${Math.floor(1000 + Math.random() * 9000)}`,
      amount: parseFloat(amount || '0'),
      due_date: dueDate,
      status: status,
    };

    try {
      if (editingInvoice) {
        await updateInvoiceMutation.mutateAsync({ id: editingInvoice.id, payload });
        setSuccessMessage(`Invoice "${editingInvoice.invoice_number}" updated.`);
      } else {
        await createInvoiceMutation.mutateAsync(payload);
        setSuccessMessage('New invoice generated successfully.');
      }
      setIsInvoiceModalOpen(false);
      resetInvoiceForm();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to save invoice.');
    }
  };

  const handleCreateRecurringSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recCustomerId.trim()) return;
    try {
      await createRecurringMutation.mutateAsync({
        customer_id: recCustomerId.trim(),
        amount: parseFloat(recAmount || '0'),
        interval: recInterval,
      });
      setSuccessMessage(`Recurring ${recInterval} invoice schedule created for ${recCustomerId.trim()}.`);
      setIsRecurringModalOpen(false);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to create recurring schedule.');
    }
  };

  const handleSendEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sendModalInvoice || !recipientEmailInput.trim()) return;
    try {
      await sendEmailMutation.mutateAsync({
        id: sendModalInvoice.id,
        recipient_email: recipientEmailInput.trim(),
      });
      setSuccessMessage(`Invoice PDF & payment link sent to ${recipientEmailInput.trim()}.`);
      setIsSendModalOpen(false);
      setSendModalInvoice(null);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to send invoice email.');
    }
  };

  const handleStripeCheckout = async (inv: InvoiceItem) => {
    try {
      const res = await stripeCheckoutMutation.mutateAsync(inv.id);
      setSuccessMessage(`Stripe Checkout session URL generated.`);
      window.open(res.checkout_url, '_blank');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to generate Stripe Checkout session.');
    }
  };

  const handleMarkPaid = async (inv: InvoiceItem) => {
    try {
      await markPaidMutation.mutateAsync({ id: inv.id, payment_method: 'Stripe Online' });
      setSuccessMessage(`Invoice "${inv.invoice_number}" marked as Paid.`);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to mark invoice as paid.');
    }
  };

  const handleExportCsv = async () => {
    try {
      const res = await exportInvoicesCsvApi();
      setSuccessMessage('Invoices list exported. Download started.');
      window.open(res.download_url, '_blank');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to export invoices CSV.');
    }
  };

  const handleImportCsv = async () => {
    try {
      const res = await importCsvMutation.mutateAsync();
      setSuccessMessage(res.message || 'Invoices CSV import processing completed.');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to import invoices CSV.');
    }
  };

  const handleBulkRemind = async () => {
    if (selectedIds.size === 0) return;
    try {
      const res = await bulkRemindMutation.mutateAsync(Array.from(selectedIds));
      setSuccessMessage(res.message || `Payment reminders sent to ${selectedIds.size} clients.`);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to send bulk payment reminders.');
    }
  };

  const handleDeleteInvoice = async () => {
    if (!invoiceToDelete) return;
    try {
      await deleteInvoiceMutation.mutateAsync(invoiceToDelete.id);
      setSuccessMessage('Invoice deleted successfully.');
      setInvoiceToDelete(null);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete invoice.');
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    try {
      const res = await bulkDeleteMutation.mutateAsync(Array.from(selectedIds));
      setSuccessMessage(`${res.affected_count || selectedIds.size} invoice(s) deleted.`);
      setSelectedIds(new Set());
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete selected invoices.');
    }
  };

  // Columns definition
  const columns: DataTableColumn<InvoiceItem>[] = [
    {
      id: 'invoice_number',
      header: 'INVOICE REF',
      cell: (item) => (
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-purple-50 border border-purple-100 flex items-center justify-center text-purple-600 font-bold shrink-0">
            <FileText className="w-4 h-4" />
          </div>
          <div>
            <div
              onClick={(e) => {
                e.stopPropagation();
                router.push(`/invoices/${item.id}`);
              }}
              className="font-bold text-slate-900 hover:text-indigo-600 cursor-pointer transition-colors text-xs"
            >
              {item.invoice_number}
            </div>
            <div className="text-[11px] text-slate-400 font-mono">Due: {item.due_date ? item.due_date.substring(0, 10) : '2026-09-01'}</div>
          </div>
        </div>
      ),
    },
    {
      id: 'amount',
      header: 'AMOUNT (USD)',
      cell: (item) => (
        <div className="flex items-center gap-1 text-slate-900 font-bold text-xs">
          <DollarSign className="w-3.5 h-3.5 text-emerald-600" />
          <span>{item.amount ? item.amount.toLocaleString(undefined, { minimumFractionDigits: 2 }) : '0.00'}</span>
        </div>
      ),
    },
    {
      id: 'status',
      header: 'STATUS',
      cell: (item) => {
        const s = item.status || 'Pending';
        const badgeStyle =
          s === 'Paid'
            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
            : s === 'Overdue'
            ? 'bg-rose-50 text-rose-700 border-rose-200'
            : s === 'Draft'
            ? 'bg-slate-100 text-slate-700 border-slate-200'
            : 'bg-amber-50 text-amber-700 border-amber-200';
        return (
          <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${badgeStyle}`}>
            {s}
          </span>
        );
      },
    },
    {
      id: 'actions',
      header: 'ACTIONS',
      cell: (item) => (
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => handleStripeCheckout(item)}
            title="Pay via Stripe Checkout"
            className="p-1.5 text-purple-600 hover:bg-purple-50 rounded-md transition-colors cursor-pointer flex items-center gap-1 text-xs font-semibold"
          >
            <CreditCard className="w-4 h-4 text-purple-600" />
            Stripe
          </button>

          <button
            onClick={() => {
              setSendModalInvoice(item);
              setIsSendModalOpen(true);
            }}
            title="Email Invoice PDF & Payment Link"
            className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-md transition-colors cursor-pointer"
          >
            <Send className="w-4 h-4" />
          </button>

          {item.status !== 'Paid' && (
            <button
              onClick={() => handleMarkPaid(item)}
              title="Mark as Paid"
              className="p-1.5 text-emerald-600 hover:bg-emerald-50 rounded-md transition-colors cursor-pointer"
            >
              <CheckCircle2 className="w-4 h-4" />
            </button>
          )}

          <button
            onClick={() => handleOpenEditModal(item)}
            title="Edit Invoice"
            className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-slate-100 rounded-md transition-colors cursor-pointer"
          >
            <Edit className="w-4 h-4" />
          </button>

          <button
            onClick={() => setInvoiceToDelete(item)}
            title="Delete Invoice"
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
            <Receipt className="w-7 h-7 text-indigo-600" />
            Invoices & Billing Gateway
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">Generate invoices, automated recurring billing, Stripe checkout links, credit memos & reminders</p>
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
            onClick={() => setIsRecurringModalOpen(true)}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer"
          >
            <Repeat className="w-4 h-4 text-amber-500" />
            Recurring Schedule
          </button>

          <button
            onClick={handleOpenCreateModal}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-semibold text-sm transition-colors shadow-sm cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            Generate Invoice
          </button>
        </div>
      </div>

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">TOTAL INVOICES</p>
            <h3 className="text-2xl font-bold text-slate-900 mt-1">{invoices.length}</h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600">
            <Receipt className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">OVERDUE UNPAID</p>
            <h3 className="text-2xl font-bold text-rose-600 mt-1">
              {overdueInvoices.length || invoices.filter((i) => i.status === 'Overdue').length}
            </h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-rose-50 flex items-center justify-center text-rose-600">
            <BellRing className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">RECURRING SCHEDULES</p>
            <h3 className="text-2xl font-bold text-amber-600 mt-1">{recurringSchedules.length} Active</h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-amber-50 flex items-center justify-center text-amber-600">
            <Repeat className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">STRIPE CHECKOUT</p>
            <h3 className="text-sm font-extrabold text-purple-600 mt-1 flex items-center gap-1.5">
              <Zap className="w-4 h-4 text-purple-500" />
              Live Online Payments
            </h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-purple-50 flex items-center justify-center text-purple-600">
            <CreditCard className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Main Data Table */}
      <DataTable<InvoiceItem>
        columns={columns}
        data={invoices}
        getRowKey={(item) => item.id}
        onRowClick={(item) => router.push(`/invoices/${item.id}`)}
        emptyTitle="No invoices found"
        emptyDescription="Generate a new invoice or adjust your status filter."
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search invoice number..."
        toolbarActions={
          <div className="flex items-center gap-3">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-700 outline-none shadow-xs"
            >
              <option value="">All Payment Statuses</option>
              <option value="Draft">Draft</option>
              <option value="Pending">Pending</option>
              <option value="Paid">Paid</option>
              <option value="Overdue">Overdue</option>
            </select>

            {selectedIds.size > 0 && (
              <div className="flex items-center gap-2 bg-indigo-50 px-3 py-1 rounded-lg border border-indigo-200">
                <span className="text-xs font-semibold text-indigo-700">{selectedIds.size} selected</span>
                <button
                  onClick={handleBulkRemind}
                  className="px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-semibold cursor-pointer"
                >
                  Send Reminders
                </button>
                <button
                  onClick={handleBulkDelete}
                  className="px-2 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded text-xs font-semibold cursor-pointer"
                >
                  Bulk Delete
                </button>
              </div>
            )}
          </div>
        }
        isLoading={isInvoicesLoading}
        pagination={{
          pageIndex: page - 1,
          pageCount: invoices.length >= limit ? page + 1 : page,
          onPageChange: (p) => setPage(p + 1),
          totalRecords: (page - 1) * limit + invoices.length,
        }}
      />

      {/* Create / Edit Invoice Modal */}
      {isInvoiceModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-5">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Receipt className="w-5 h-5 text-indigo-600" />
                {editingInvoice ? 'Edit Invoice' : 'Generate New Invoice'}
              </h2>
              <button onClick={() => setIsInvoiceModalOpen(false)} className="text-slate-400 hover:text-slate-600 p-1 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveInvoiceSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                  Invoice Reference Number
                </label>
                <input
                  type="text"
                  value={invoiceNumber}
                  onChange={(e) => setInvoiceNumber(e.target.value)}
                  placeholder="e.g. INV-2026-001"
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none font-mono"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                    Invoice Amount (USD) *
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                    Payment Status
                  </label>
                  <select
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                  >
                    <option value="Draft">Draft</option>
                    <option value="Pending">Pending</option>
                    <option value="Paid">Paid</option>
                    <option value="Overdue">Overdue</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                  Payment Due Date
                </label>
                <input
                  type="date"
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
                <button type="button" onClick={() => setIsInvoiceModalOpen(false)} className="px-4 py-2 text-sm font-medium text-slate-600">
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createInvoiceMutation.isPending || updateInvoiceMutation.isPending}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-lg font-medium text-sm cursor-pointer shadow-sm disabled:opacity-50"
                >
                  {(createInvoiceMutation.isPending || updateInvoiceMutation.isPending) && (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  )}
                  {editingInvoice ? 'Save Changes' : 'Generate Invoice'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create Recurring Invoice Modal */}
      {isRecurringModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Repeat className="w-5 h-5 text-amber-500" />
                Create Recurring Billing Schedule
              </h3>
              <button onClick={() => setIsRecurringModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateRecurringSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Customer / Client Name *</label>
                <input
                  type="text"
                  required
                  value={recCustomerId}
                  onChange={(e) => setRecCustomerId(e.target.value)}
                  placeholder="e.g. Acme Global Corp"
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-amber-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Recurring Amount</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={recAmount}
                    onChange={(e) => setRecAmount(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Billing Cycle</label>
                  <select
                    value={recInterval}
                    onChange={(e) => setRecInterval(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-amber-500"
                  >
                    <option value="Monthly">Monthly</option>
                    <option value="Quarterly">Quarterly</option>
                    <option value="Annual">Annual</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setIsRecurringModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createRecurringMutation.isPending}
                  className="flex items-center gap-2 bg-amber-600 hover:bg-amber-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
                >
                  {createRecurringMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Create Schedule
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Send Invoice Email Modal */}
      {isSendModalOpen && sendModalInvoice && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Send className="w-5 h-5 text-blue-600" />
                Email Invoice & Payment Link
              </h3>
              <button onClick={() => setIsSendModalOpen(false)} className="text-slate-400 hover:text-slate-600">
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
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setIsSendModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
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
          </div>
        </div>
      )}

      {/* Confirm Delete Modal */}
      {invoiceToDelete && (
        <ConfirmModal
          isOpen={!!invoiceToDelete}
          title="Delete Invoice"
          description={`Are you sure you want to delete invoice "${invoiceToDelete.invoice_number}"?`}
          confirmText="Delete Invoice"
          variant="danger"
          onConfirm={handleDeleteInvoice}
          onClose={() => setInvoiceToDelete(null)}
        />
      )}
    </div>
  );
}
