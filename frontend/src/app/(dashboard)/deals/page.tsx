'use client';

import { ResponsiveSelect } from '@/components/common/responsive-select';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Briefcase,
  Plus,
  FileSpreadsheet,
  Upload,
  Trash2,
  Edit,
  CheckCircle2,
  AlertCircle,
  Trophy,
  XCircle,
  Copy,
  User,
} from 'lucide-react';
import { ActionMenu } from '@/components/common/action-menu';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { PermissionGate } from '@/components/common/permission-gate';
import { PERMISSIONS } from '@/lib/permissions';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { ModalShell } from '@/components/common/modal-shell';
import { DealCustomFields } from '@/components/features/deals/deal-custom-fields';
import {
  useDealsQuery,
  useCreateDealMutation,
  useUpdateDealMutation,
  useDeleteDealMutation,
  useMarkDealWonMutation,
  useMarkDealLostMutation,
  useBulkDeleteDealsMutation,
  useImportDealsCsvMutation,
  useDealCustomFieldsQuery,
  exportDealsCsvApi,
  importDealsCsvApi,
  cloneDealApi,
  DealItem
} from '@/lib/api/deals';
import { useUsersQuery } from '@/lib/api/users';

const STAGES = ['Prospecting', 'Qualification', 'Proposal', 'Negotiation', 'Closed Won', 'Closed Lost'];

export default function DealsPage() {
  const router = useRouter();
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [page, setPage] = useState(1);
  const limit = 20;

  const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(new Set());
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Modals
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [dealToEdit, setDealToEdit] = useState<DealItem | null>(null);
  const [dealToDelete, setDealToDelete] = useState<DealItem | null>(null);

  // Form State
  const [formTitle, setFormTitle] = useState('');
  const [formAmount, setFormAmount] = useState<number | ''>('');
  const [formStage, setFormStage] = useState('Prospecting');
  const [formProbability, setFormProbability] = useState<number | ''>(10);
  const [formAssignedTo, setFormAssignedTo] = useState('');
  const [formCustomFields, setFormCustomFields] = useState<Record<string, string | number | boolean | null>>({});

  // Search Debounce
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
      setPage(1);
    }, 250);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  // Queries
  const { data: deals = [], refetch: refetchDeals } = useDealsQuery(page, limit, undefined, debouncedSearchTerm);
  const { data: users = [] } = useUsersQuery();
  const {
    data: customFields = [],
    isLoading: isCustomFieldsLoading,
    isError: isCustomFieldsError,
  } = useDealCustomFieldsQuery(isCreateModalOpen || isEditModalOpen);

  // Mutations
  const createDealMutation = useCreateDealMutation();
  const updateDealMutation = useUpdateDealMutation();
  const deleteDealMutation = useDeleteDealMutation();
  const markWonMutation = useMarkDealWonMutation();
  const markLostMutation = useMarkDealLostMutation();
  const bulkDeleteMutation = useBulkDeleteDealsMutation();
  const importCsvMutation = useImportDealsCsvMutation();

  const refetchAll = () => {
    refetchDeals();
  };

  const resetForm = () => {
    setFormTitle('');
    setFormAmount('');
    setFormStage('Prospecting');
    setFormProbability(10);
    setFormAssignedTo(users[0]?.id || '');
    setFormCustomFields({});
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formTitle) {
      setErrorMessage('Please enter a deal title.');
      return;
    }
    try {
      setErrorMessage(null);
      await createDealMutation.mutateAsync({
        title: formTitle,
        amount: Number(formAmount) || 0,
        stage: formStage,
        probability: formProbability !== '' ? Number(formProbability) : undefined,
        assigned_to: formAssignedTo || undefined,
        custom_fields: formCustomFields,
      });
      setSuccessMessage(`Deal '${formTitle}' created successfully.`);
      setIsCreateModalOpen(false);
      resetForm();
      refetchAll();
    } catch {
      setErrorMessage('Failed to create sales deal.');
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dealToEdit) return;
    try {
      setErrorMessage(null);
      await updateDealMutation.mutateAsync({
        id: dealToEdit.id,
        data: {
          title: formTitle,
          amount: Number(formAmount) || 0,
          stage: formStage,
          probability: formProbability !== '' ? Number(formProbability) : undefined,
          assigned_to: formAssignedTo || undefined,
          custom_fields: formCustomFields,
        },
      });
      setSuccessMessage(`Deal '${formTitle}' updated successfully.`);
      setIsEditModalOpen(false);
      setDealToEdit(null);
      resetForm();
      refetchAll();
    } catch {
      setErrorMessage('Failed to update deal.');
    }
  };

  const openEditModal = (item: DealItem) => {
    setDealToEdit(item);
    setFormTitle(item.title);
    setFormAmount(item.amount);
    setFormStage(item.stage);
    setFormProbability(item.probability ?? 10);
    setFormAssignedTo(item.assigned_to || '');
    setFormCustomFields(item.custom_fields ?? {});
    setIsEditModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!dealToDelete) return;
    try {
      setErrorMessage(null);
      await deleteDealMutation.mutateAsync(dealToDelete.id);
      setSuccessMessage(`Deal '${dealToDelete.title}' deleted successfully.`);
      setDealToDelete(null);
      refetchAll();
    } catch {
      setErrorMessage('Failed to delete deal.');
      setDealToDelete(null);
    }
  };

  const handleMarkWon = async (item: DealItem) => {
    try {
      await markWonMutation.mutateAsync({ id: item.id, final_amount: item.amount });
      setSuccessMessage(`Deal '${item.title}' marked as Closed Won! ðŸŽ‰`);
      refetchAll();
    } catch {
      setErrorMessage('Failed to mark deal as won.');
    }
  };

  const handleMarkLost = async (item: DealItem) => {
    try {
      await markLostMutation.mutateAsync({ id: item.id, reason: 'Budget constraints' });
      setSuccessMessage(`Deal '${item.title}' marked as Closed Lost.`);
      refetchAll();
    } catch {
      setErrorMessage('Failed to mark deal as lost.');
    }
  };

  const handleCloneDeal = async (item: DealItem) => {
    try {
      const cloned = await cloneDealApi({ id: item.id, new_title: `${item.title} (Copy)` });
      setSuccessMessage(`Cloned deal '${cloned.title}' successfully.`);
      refetchAll();
    } catch {
      setErrorMessage('Failed to clone deal.');
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    if (confirm(`Delete ${selectedIds.size} selected deal(s)?`)) {
      try {
        setErrorMessage(null);
        await bulkDeleteMutation.mutateAsync(Array.from(selectedIds));
        setSuccessMessage(`${selectedIds.size} deal(s) deleted successfully.`);
        setSelectedIds(new Set());
        refetchAll();
      } catch {
        setErrorMessage('Failed to bulk delete deals.');
      }
    }
  };

  const handleExportCsv = async () => {
    try {
      const res = await exportDealsCsvApi();
      setSuccessMessage(`Deals CSV exported. Download URL: ${res.download_url}`);
    } catch {
      setErrorMessage('Failed to export deals CSV.');
    }
  };

  const handleImportCsv = async () => {
    try {
      const res = await importDealsCsvApi();
      setSuccessMessage(res.message || 'Deals imported from CSV successfully.');
      refetchAll();
    } catch {
      setErrorMessage('Failed to import deals CSV.');
    }
  };

  const columns: DataTableColumn<DealItem>[] = [
    {
      id: 'title',
      header: 'Deal Title',
      cell: (item) => (
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100 text-blue-700 font-bold text-xs shrink-0">
            <Briefcase className="w-4 h-4" />
          </div>
          <div>
            <Link href={`/deals/${item.id}`} className="font-bold text-slate-900 text-xs hover:text-blue-600 hover:underline">
              {item.title}
            </Link>
            <div className="text-[11px] text-slate-500">Close Date: {item.expected_close_date || 'TBD'}</div>
          </div>
        </div>
      ),
    },
    {
      id: 'amount',
      header: 'Deal Amount',
      cell: (item) => (
        <div className="font-bold text-blue-700 text-xs">
          ${item.amount ? item.amount.toLocaleString() : '0'}
        </div>
      ),
    },
    {
      id: 'stage',
      header: 'Pipeline Stage',
      cell: (item) => {
        let badgeStyle = 'bg-slate-100 text-slate-700 border-slate-200';
        if (item.stage === 'Closed Won') badgeStyle = 'bg-emerald-50 text-emerald-700 border-emerald-200 font-bold';
        else if (item.stage === 'Closed Lost') badgeStyle = 'bg-rose-50 text-rose-700 border-rose-200';
        else if (item.stage === 'Proposal' || item.stage === 'Negotiation') badgeStyle = 'bg-blue-50 text-blue-700 border-blue-200';

        return (
          <Badge variant="outline" className={`text-[11px] px-2 py-0.5 ${badgeStyle}`}>
            {item.stage}
          </Badge>
        );
      },
    },
    {
      id: 'probability',
      header: 'Win Rate %',
      cell: (item) => (
        <div className="text-xs font-semibold text-slate-700">
          {item.probability ? `${item.probability}%` : 'N/A'}
        </div>
      ),
    },
    {
      id: 'assigned_to',
      header: 'Sales Rep',
      cell: (item) => {
        const assignedUser = users.find((u) => u.id === item.assigned_to);
        return (
          <div className="flex items-center gap-1.5 text-xs text-slate-600 font-medium">
            <User className="w-3.5 h-3.5 text-slate-400 shrink-0" />
            <span>{assignedUser ? assignedUser.name || assignedUser.email : item.assigned_to || 'Unassigned'}</span>
          </div>
        );
      },
    },
  ];

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2.5">
            <Briefcase className="w-6 h-6 text-blue-600" />
            <span>Sales Deals & Pipeline</span>
          </h1>
          <p className="text-xs font-medium text-slate-500 mt-1">
            Manage interactive Kanban stages, win probability metrics, and closed sales deals.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">

          <PermissionGate permission={PERMISSIONS.DEALS.CREATE}>
            <Button
              size="sm"
              onClick={() => {
                resetForm();
                setIsCreateModalOpen(true);
              }}
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs gap-1.5 cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>Add Deal</span>
            </Button>
          </PermissionGate>

          <ActionMenu
            label="More"
            className="h-8 text-xs font-semibold"
            actions={[
              {
                label: 'Export CSV',
                permission: PERMISSIONS.DEALS.EXPORT,
                icon: <FileSpreadsheet className="w-4 h-4 text-emerald-600" />,
                onSelect: handleExportCsv,
              },
              {
                label: 'Import CSV',
                permission: PERMISSIONS.DEALS.IMPORT,
                icon: <Upload className="w-4 h-4 text-blue-600" />,
                disabled: importCsvMutation.isPending,
                onSelect: handleImportCsv,
              },
            ]}
          />

          {selectedIds.size > 0 && (
            <PermissionGate permission={PERMISSIONS.DEALS.BULK_DELETE}>
              <Button
                size="sm"
                variant="outline"
                onClick={handleBulkDelete}
                className="border-rose-300 text-rose-600 hover:bg-rose-50 font-semibold text-xs gap-1 cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Delete Selected ({selectedIds.size})</span>
              </Button>
            </PermissionGate>
          )}
        </div>
      </div>

      {/* Feedback Banners */}
      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs font-medium flex items-center gap-2 animate-in fade-in-50">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs font-medium flex items-center gap-2 animate-in fade-in-50">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}
      {/* DATATABLE */}
      <DataTable
          columns={columns}
          data={deals}
          getRowKey={(item) => item.id}
          onRowClick={(item) => router.push(`/deals/${item.id}`)}
          searchValue={searchTerm}
          onSearchChange={setSearchTerm}
          searchPlaceholder="Search deals by title..."
          actionVariant="menu"
          actions={(item) => [
            {
              label: 'Edit Deal',
              permission: PERMISSIONS.DEALS.UPDATE,
              icon: <Edit className="w-4 h-4 text-blue-600 mr-2" />,
              onClick: () => openEditModal(item),
            },
            {
              label: 'Mark as Won',
              permission: PERMISSIONS.DEALS.UPDATE,
              icon: <Trophy className="w-4 h-4 text-emerald-600 mr-2" />,
              onClick: () => handleMarkWon(item),
            },
            {
              label: 'Mark as Lost',
              permission: PERMISSIONS.DEALS.UPDATE,
              icon: <XCircle className="w-4 h-4 text-rose-600 mr-2" />,
              onClick: () => handleMarkLost(item),
            },
            {
              label: 'Clone Deal',
              permission: PERMISSIONS.DEALS.CREATE,
              icon: <Copy className="w-4 h-4 text-indigo-600 mr-2" />,
              onClick: () => handleCloneDeal(item),
            },
            {
              label: 'Delete Deal',
              variant: 'destructive',
              permission: PERMISSIONS.DEALS.DELETE,
              icon: <Trash2 className="w-4 h-4 text-rose-600 mr-2" />,
              onClick: () => setDealToDelete(item),
            },
          ]}
          emptyTitle="No sales deals found"
          emptyDescription="Create your first deal or import pipeline CSV data."
          showCheckbox
          selectedIds={selectedIds}
          onToggleAllRows={(checked) => {
            if (checked) {
              setSelectedIds(new Set(deals.map((d) => d.id)));
            } else {
              setSelectedIds(new Set());
            }
          }}
          onToggleRow={(item, checked) => {
            const next = new Set(selectedIds);
            if (checked) next.add(item.id);
            else next.delete(item.id);
            setSelectedIds(next);
          }}
          pagination={{
            pageIndex: page - 1,
            pageCount: Math.ceil((deals.length || 1) / limit) || 1,
            onPageChange: (pIndex) => setPage(pIndex + 1),
            totalRecords: deals.length,
          }}
        />
      
      {/* CREATE DEAL MODAL */}
      {isCreateModalOpen && (
        <ModalShell
          isOpen={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
          title={
            <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
              <Briefcase className="w-5 h-5 text-blue-600" />
              <span>Create New Sales Deal</span>
            </h3>
          }
        >
          <form onSubmit={handleCreateSubmit} className="space-y-4 text-xs">
            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Deal Title</Label>
              <Input
                type="text"
                placeholder="e.g. Acme Corp Enterprise License"
                value={formTitle}
                onChange={(e) => setFormTitle(e.target.value)}
                className="h-9 text-xs"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Amount ($)</Label>
                <Input
                  type="number"
                  placeholder="45000"
                  value={formAmount}
                  onChange={(e) => setFormAmount(e.target.value !== '' ? Number(e.target.value) : '')}
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Pipeline Stage</Label>
                <ResponsiveSelect
                  value={formStage}
                  onValueChange={setFormStage}
                  className="w-full h-9 rounded-md border border-slate-200 bg-white px-3 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
                >
                  {STAGES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </ResponsiveSelect>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Win Probability (%)</Label>
                <Input
                  type="number"
                  placeholder="50"
                  value={formProbability}
                  onChange={(e) => setFormProbability(e.target.value !== '' ? Number(e.target.value) : '')}
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Assigned Sales Rep</Label>
                <ResponsiveSelect
                  value={formAssignedTo}
                  onValueChange={setFormAssignedTo}
                  className="w-full h-9 rounded-md border border-slate-200 bg-white px-3 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
                >
                  <option value="">-- Select Sales Rep --</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.name || u.email} ({u.email})
                    </option>
                  ))}
                </ResponsiveSelect>
              </div>
            </div>

            <DealCustomFields
              fields={customFields}
              values={formCustomFields}
              onChange={(fieldName, value) => {
                setFormCustomFields((current) => ({ ...current, [fieldName]: value }));
              }}
              isLoading={isCustomFieldsLoading}
              isError={isCustomFieldsError}
            />

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setIsCreateModalOpen(false)} className="cursor-pointer">
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={createDealMutation.isPending} className="bg-blue-600 text-white font-semibold cursor-pointer">
                {createDealMutation.isPending ? 'Creating...' : 'Create Deal'}
              </Button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* EDIT DEAL MODAL */}
      {isEditModalOpen && (
        <ModalShell
          isOpen={isEditModalOpen}
          onClose={() => setIsEditModalOpen(false)}
          title={
            <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
              <Edit className="w-5 h-5 text-blue-600" />
              <span>Edit Sales Deal</span>
            </h3>
          }
        >
          <form onSubmit={handleEditSubmit} className="space-y-4 text-xs">
            <div className="space-y-1">
              <Label className="font-semibold text-slate-700">Deal Title</Label>
              <Input
                type="text"
                value={formTitle}
                onChange={(e) => setFormTitle(e.target.value)}
                className="h-9 text-xs"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Amount ($)</Label>
                <Input
                  type="number"
                  value={formAmount}
                  onChange={(e) => setFormAmount(e.target.value !== '' ? Number(e.target.value) : '')}
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Pipeline Stage</Label>
                <ResponsiveSelect
                  value={formStage}
                  onValueChange={setFormStage}
                  className="w-full h-9 rounded-md border border-slate-200 bg-white px-3 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
                >
                  {STAGES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </ResponsiveSelect>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Win Probability (%)</Label>
                <Input
                  type="number"
                  value={formProbability}
                  onChange={(e) => setFormProbability(e.target.value !== '' ? Number(e.target.value) : '')}
                  className="h-9 text-xs"
                />
              </div>

              <div className="space-y-1">
                <Label className="font-semibold text-slate-700">Assigned Sales Rep</Label>
                <ResponsiveSelect
                  value={formAssignedTo}
                  onValueChange={setFormAssignedTo}
                  className="w-full h-9 rounded-md border border-slate-200 bg-white px-3 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
                >
                  <option value="">-- Select Sales Rep --</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.name || u.email} ({u.email})
                    </option>
                  ))}
                </ResponsiveSelect>
              </div>
            </div>

            <DealCustomFields
              fields={customFields}
              values={formCustomFields}
              onChange={(fieldName, value) => {
                setFormCustomFields((current) => ({ ...current, [fieldName]: value }));
              }}
              isLoading={isCustomFieldsLoading}
              isError={isCustomFieldsError}
            />

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setIsEditModalOpen(false)} className="cursor-pointer">
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={updateDealMutation.isPending} className="bg-blue-600 text-white font-semibold cursor-pointer">
                {updateDealMutation.isPending ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* DELETE CONFIRM MODAL */}
      <ConfirmModal
        isOpen={!!dealToDelete}
        onClose={() => setDealToDelete(null)}
        onConfirm={handleConfirmDelete}
        title="Delete Sales Deal"
        description="This action cannot be undone."
        confirmText="Delete Deal"
        variant="danger"
        isLoading={deleteDealMutation.isPending}
        message={
          dealToDelete && (
            <p>
              Are you sure you want to delete sales deal <strong className="text-slate-900">{dealToDelete.title}</strong> (${dealToDelete.amount?.toLocaleString()})?
            </p>
          )
        }
      />
    </div>
  );
}
