'use client';

import { ResponsiveSelect } from '@/components/common/responsive-select';

import { ActionMenu } from '@/components/common/action-menu';
import { Button } from '@/components/ui/button';
import { getErrorMessage } from '@/lib/utils';
import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  FileText,
  DollarSign,
  Plus,
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
  Repeat,
  Receipt
} from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { ModalShell } from '@/components/common/modal-shell';
import { PermissionGate } from '@/components/common/permission-gate';
import { PERMISSIONS } from '@/lib/permissions';
import {
  useInvoicesQuery,
  useCreateInvoiceMutation,
  useUpdateInvoiceMutation,
  useDeleteInvoiceMutation,
  useBulkDeleteInvoicesMutation,
  useBulkRemindInvoicesMutation,
  useSendInvoiceEmailMutation,
  useCreateStripeCheckoutMutation,
  useMarkInvoicePaidMutation,
  useCreateRecurringInvoiceMutation,
  useImportInvoicesCsvMutation,
  exportInvoicesCsvApi,
  InvoiceItem,
  InvoiceCreatePayload
} from '@/lib/api/invoices';
import { useDealsQuery } from '@/lib/api/deals';

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
  const [formDealId, setFormDealId] = useState('');
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

  // Only Closed Won deals are invoiceable (backend enforces the same rule).
  const { data: closedWonDeals = [] } = useDealsQuery(1, 100, 'Closed Won');

  // Mutations
  const createInvoiceMutation = useCreateInvoiceMutation();
  const updateInvoiceMutation = useUpdateInvoiceMutation();
  const deleteInvoiceMutation = useDeleteInvoiceMutation();
  const bulkDeleteMutation = useBulkDeleteInvoicesMutation();
  const bulkRemindMutation = useBulkRemindInvoicesMutation();
  const sendEmailMutation = useSendInvoiceEmailMutation();
  const stripeCheckoutMutation = useCreateStripeCheckoutMutation();
  const markPaidMutation = useMarkInvoicePaidMutation();
  const createRecurringMutation = useCreateRecurringInvoiceMutation();
  const importCsvMutation = useImportInvoicesCsvMutation();

  const resetInvoiceForm = () => {
    setFormDealId('');
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

    try {
      if (editingInvoice) {
        const payload: InvoiceCreatePayload = {
          deal_id: editingInvoice.deal_id || '',
          invoice_number: invoiceNumber.trim(),
          amount: parseFloat(amount || '0'),
          due_date: dueDate,
          status: status,
        };
        await updateInvoiceMutation.mutateAsync({ id: editingInvoice.id, payload });
        setSuccessMessage(`Invoice "${editingInvoice.invoice_number}" updated.`);
      } else {
        if (!formDealId) {
          setErrorMessage('Select a Closed Won deal to generate an invoice.');
          return;
        }
        const payload: InvoiceCreatePayload = {
          deal_id: formDealId,
          due_date: dueDate,
        };
        const created = await createInvoiceMutation.mutateAsync(payload);
        setSuccessMessage(`Invoice '${created.invoice_number}' generated as Draft.`);
      }
      setIsInvoiceModalOpen(false);
      resetInvoiceForm();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to save invoice.';
      setErrorMessage(message);
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
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to create recurring schedule.'));
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
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to send invoice email.'));
    }
  };

  const handleStripeCheckout = async (inv: InvoiceItem) => {
    try {
      const res = await stripeCheckoutMutation.mutateAsync(inv.id);
      setSuccessMessage(`Stripe Checkout session URL generated.`);
      window.open(res.checkout_url, '_blank');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to generate Stripe Checkout session.'));
    }
  };

  const handleMarkPaid = async (inv: InvoiceItem) => {
    try {
      await markPaidMutation.mutateAsync({ id: inv.id, payment_method: 'Stripe Online' });
      setSuccessMessage(`Invoice "${inv.invoice_number}" marked as Paid.`);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to mark invoice as paid.'));
    }
  };

  const handleExportCsv = async () => {
    try {
      const res = await exportInvoicesCsvApi();
      setSuccessMessage('Invoices list exported. Download started.');
      window.open(res.download_url, '_blank');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to export invoices CSV.'));
    }
  };

  const handleImportCsv = async () => {
    try {
      const res = await importCsvMutation.mutateAsync();
      setSuccessMessage(res.message || 'Invoices CSV import processing completed.');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to import invoices CSV.'));
    }
  };

  const handleBulkRemind = async () => {
    if (selectedIds.size === 0) return;
    try {
      const res = await bulkRemindMutation.mutateAsync(Array.from(selectedIds));
      setSuccessMessage(res.message || `Payment reminders sent to ${selectedIds.size} clients.`);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to send bulk payment reminders.'));
    }
  };

  const handleDeleteInvoice = async () => {
    if (!invoiceToDelete) return;
    try {
      await deleteInvoiceMutation.mutateAsync(invoiceToDelete.id);
      setSuccessMessage('Invoice deleted successfully.');
      setInvoiceToDelete(null);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to delete invoice.'));
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    try {
      const res = await bulkDeleteMutation.mutateAsync(Array.from(selectedIds));
      setSuccessMessage(`${res.affected_count || selectedIds.size} invoice(s) deleted.`);
      setSelectedIds(new Set());
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to delete selected invoices.'));
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
        <ActionMenu
          iconOnly
          label="Open invoice actions"
          onTriggerClick={(event) => event.stopPropagation()}
          actions={[
            { label: 'Stripe checkout', permission: PERMISSIONS.INVOICES.PAYMENT, icon: <CreditCard className="w-4 h-4 text-purple-600" />, onSelect: () => handleStripeCheckout(item) },
            { label: 'Send invoice email', permission: PERMISSIONS.INVOICES.SEND, icon: <Send className="w-4 h-4 text-blue-600" />, onSelect: () => { setSendModalInvoice(item); setIsSendModalOpen(true); } },
            ...(item.status !== 'Paid' ? [{ label: 'Mark as paid', permission: PERMISSIONS.INVOICES.PAYMENT, icon: <CheckCircle2 className="w-4 h-4 text-emerald-600" />, onSelect: () => handleMarkPaid(item) }] : []),
            { label: 'Edit invoice', permission: PERMISSIONS.INVOICES.UPDATE, icon: <Edit className="w-4 h-4 text-indigo-600" />, onSelect: () => handleOpenEditModal(item) },
            { label: 'Delete invoice', permission: PERMISSIONS.INVOICES.DELETE, icon: <Trash2 className="w-4 h-4" />, variant: 'destructive', onSelect: () => setInvoiceToDelete(item) },
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
            <Receipt className="w-7 h-7 text-indigo-600" />
            Invoices & Billing Gateway
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">Generate invoices, automated recurring billing, Stripe checkout links, credit memos & reminders</p>
        </div>

        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <PermissionGate permission={PERMISSIONS.INVOICES.CREATE}>
            <Button onClick={handleOpenCreateModal} className="w-full gap-2 text-xs font-semibold sm:w-auto">
              <Plus className="w-4 h-4" />Generate Invoice
            </Button>
          </PermissionGate>
          <ActionMenu label="More" className="w-full text-xs font-semibold sm:w-auto" actions={[
            { label: 'Export CSV', icon: <Download className="w-4 h-4 text-slate-600" />, onSelect: handleExportCsv },
            { label: 'Import CSV', icon: importCsvMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4 text-indigo-600" />, disabled: importCsvMutation.isPending, onSelect: handleImportCsv },
            { label: 'Recurring schedule', icon: <Repeat className="w-4 h-4 text-amber-500" />, onSelect: () => setIsRecurringModalOpen(true) },
          ]} />
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
            <ResponsiveSelect
              value={statusFilter}
              onValueChange={setStatusFilter}
              className="bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-700 outline-none shadow-xs"
            >
              <option value="">All Payment Statuses</option>
              <option value="Draft">Draft</option>
              <option value="Pending">Pending</option>
              <option value="Paid">Paid</option>
              <option value="Overdue">Overdue</option>
            </ResponsiveSelect>

            {selectedIds.size > 0 && (
              <div className="flex w-full flex-wrap items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1 sm:w-auto">
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
        <ModalShell
          isOpen={isInvoiceModalOpen}
          onClose={() => setIsInvoiceModalOpen(false)}
          size="lg"
          title={
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Receipt className="w-5 h-5 text-indigo-600" />
              {editingInvoice ? 'Edit Invoice' : 'Generate New Invoice'}
            </h2>
          }
        >
          <form onSubmit={handleSaveInvoiceSubmit} className="space-y-4">
            {!editingInvoice && (
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                  Closed Won Deal *
                </label>
                <ResponsiveSelect
                  required
                  value={formDealId}
                  onValueChange={setFormDealId}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                >
                  <option value="">-- Select a Closed Won deal --</option>
                  {closedWonDeals.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.title} (${d.amount ? d.amount.toLocaleString() : '0'})
                    </option>
                  ))}
                </ResponsiveSelect>
                <p className="text-[11px] text-slate-400 mt-1">
                  Invoices are generated from Closed Won deals. Amount and line items are derived
                  from the deal.
                </p>
              </div>
            )}

            {editingInvoice && (
              <>
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

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
                    <ResponsiveSelect
                      value={status}
                      onValueChange={setStatus}
                      className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                    >
                      <option value="Draft">Draft</option>
                      <option value="Pending">Pending</option>
                      <option value="Paid">Paid</option>
                      <option value="Overdue">Overdue</option>
                    </ResponsiveSelect>
                  </div>
                </div>
              </>
            )}

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

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-3 pt-3 border-t border-slate-100">
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
        </ModalShell>
      )}

      {/* Create Recurring Invoice Modal */}
      {isRecurringModalOpen && (
        <ModalShell
          isOpen={isRecurringModalOpen}
          onClose={() => setIsRecurringModalOpen(false)}
          size="md"
          title={
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Repeat className="w-5 h-5 text-amber-500" />
              Create Recurring Billing Schedule
            </h3>
          }
        >
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

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
                <ResponsiveSelect
                  value={recInterval}
                  onValueChange={setRecInterval}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-amber-500"
                >
                  <option value="Monthly">Monthly</option>
                  <option value="Quarterly">Quarterly</option>
                  <option value="Annual">Annual</option>
                </ResponsiveSelect>
              </div>
            </div>

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-3 pt-2">
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
        </ModalShell>
      )}

      {/* Send Invoice Email Modal */}
      {isSendModalOpen && sendModalInvoice && (
        <ModalShell
          isOpen={isSendModalOpen}
          onClose={() => setIsSendModalOpen(false)}
          size="md"
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

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-3 pt-2">
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
        </ModalShell>
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
