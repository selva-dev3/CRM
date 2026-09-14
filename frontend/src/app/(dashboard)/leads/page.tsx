'use client';

import { ResponsiveSelect } from '@/components/common/responsive-select';

import React, { useState, useMemo, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { 
  Plus, 
  Building2, 
  Mail, 
  Phone, 
  X, 
  Loader2, 
  CheckCircle2, 
  AlertCircle,
  Sparkles,
  RefreshCw,
  Pencil,
  Trash2,
  User,
  Sliders,
  ChevronDown,
  Archive,
  UserCheck,
  RotateCcw,
  Search
} from 'lucide-react';
import { 
  Button, 
  Label, 
  Input, 
  Alert, 
  AlertDescription,
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator
} from '@/components/ui';
import { DataTable, DataTableColumn, TableActionOption } from '@/components/common/data-table';
import { ModalShell } from '@/components/common/modal-shell';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { PermissionGate } from '@/components/common/permission-gate';
import { LeadFormDialog } from '@/components/features/leads/lead-form-dialog';
import { PERMISSIONS } from '@/lib/permissions';
import { 
  useLeadsQuery, 
  useDeleteLeadMutation, 
  useBulkDeleteLeadsMutation,
  useBulkArchiveLeadsMutation,
  useArchiveLeadMutation,
  useUnarchiveLeadMutation,
  useAssignLeadMutation,
  Lead 
} from '@/lib/api/leads';
import { useUsersQuery } from '@/lib/api/users';

const LEAD_STATUS_OPTIONS = ['New', 'Contacted', 'Qualified', 'Unqualified', 'Converted'] as const;
const LEAD_SOURCE_OPTIONS = ['Website', 'LinkedIn', 'Referral', 'Cold Call', 'Event', 'Partner'] as const;

const STATUS_STYLES: Record<(typeof LEAD_STATUS_OPTIONS)[number], string> = {
  New: 'bg-blue-50 text-blue-800 border-blue-200',
  Contacted: 'bg-amber-50 text-amber-800 border-amber-200',
  Qualified: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  Unqualified: 'bg-slate-100 text-slate-800 border-slate-200',
  Converted: 'bg-purple-50 text-purple-800 border-purple-200',
};

function canonicalLeadStatus(value: string): (typeof LEAD_STATUS_OPTIONS)[number] | null {
  return LEAD_STATUS_OPTIONS.find((status) => status.toLowerCase() === value.trim().toLowerCase()) ?? null;
}

function formatLeadSource(value: string): string {
  const trimmed = value.trim();
  const canonical = LEAD_SOURCE_OPTIONS.find((source) => source.toLowerCase() === trimmed.toLowerCase());
  if (canonical) return canonical;
  if (/^https?:\/\//i.test(trimmed)) return 'Website';
  return trimmed || 'Unknown';
}

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

export default function LeadsPage() {
  const router = useRouter();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingLead, setEditingLead] = useState<Lead | null>(null);
  const [leadToDelete, setLeadToDelete] = useState<Lead | null>(null);
  const [bulkDeleteIds, setBulkDeleteIds] = useState<string[] | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [page, setPage] = useState(1);
  const limit = 15;
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Debounce search input to avoid refetching API on every single character typed
  useEffect(() => {
    if (searchTerm === debouncedSearchTerm) return;
    const timer = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
      setPage(1);
      setSelectedIds(new Set());
    }, 250);
    return () => clearTimeout(timer);
  }, [searchTerm, debouncedSearchTerm]);

  // Feedback Banner State
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // TanStack Query Hooks for Leads, Organizations, Companies & Users API
  const { data: leadsPage, isLoading, isError, error: leadsError, refetch } = useLeadsQuery({
    page,
    limit,
    search: debouncedSearchTerm || undefined,
    status: statusFilter || undefined,
  });
  const leads = leadsPage?.items ?? [];
  const totalLeads = leadsPage?.total ?? 0;

  const [userSearchTerm, setUserSearchTerm] = useState<string>('');
  const [debouncedUserSearchTerm, setDebouncedUserSearchTerm] = useState<string>('');

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedUserSearchTerm(userSearchTerm);
    }, 250);
    return () => clearTimeout(timer);
  }, [userSearchTerm]);

  const { data: users = [] } = useUsersQuery(1, 100, debouncedUserSearchTerm || undefined);

  const [assigningLead, setAssigningLead] = useState<Lead | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<string>('');

  const deleteLeadMutation = useDeleteLeadMutation();
  const bulkDeleteMutation = useBulkDeleteLeadsMutation();
  const bulkArchiveMutation = useBulkArchiveLeadsMutation();
  const archiveLeadMutation = useArchiveLeadMutation();
  const unarchiveLeadMutation = useUnarchiveLeadMutation();
  const assignLeadMutation = useAssignLeadMutation();

  const handleToggleRow = (item: Lead, checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(item.id);
      else next.delete(item.id);
      return next;
    });
  };

  const handleToggleAllRows = (checked: boolean) => {
    setSelectedIds((previous) => {
      const next = new Set(previous);
      for (const lead of leads) {
        if (checked) next.add(lead.id);
        else next.delete(lead.id);
      }
      return next;
    });
  };

  const handleConfirmBulkDelete = async () => {
    if (!bulkDeleteIds?.length) return;
    try {
      setErrorMessage(null);
      const result = await bulkDeleteMutation.mutateAsync(bulkDeleteIds);
      setSuccessMessage(`Successfully deleted ${result.affected_count} selected lead(s).`);
      setSelectedIds(new Set());
      setBulkDeleteIds(null);
      if (page > 1 && totalLeads - result.affected_count <= (page - 1) * limit) {
        setPage((current) => Math.max(1, current - 1));
      }
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, 'Bulk delete failed. Please try again.'));
    }
  };

  const handleBulkArchive = async () => {
    if (selectedIds.size === 0) return;
    try {
      setErrorMessage(null);
      const ids = Array.from(selectedIds);
      const result = await bulkArchiveMutation.mutateAsync(ids);
      setSuccessMessage(`Successfully archived ${result.affected_count} selected lead(s).`);
      setSelectedIds(new Set());
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, 'Bulk archive failed. Please try again.'));
    }
  };

  const handleConfirmDelete = async () => {
    if (!leadToDelete) return;
    try {
      setErrorMessage(null);
      await deleteLeadMutation.mutateAsync(leadToDelete.id);
      setSuccessMessage(`Lead "${leadToDelete.contact_name}" deleted successfully!`);
      setLeadToDelete(null);
      if (page > 1 && totalLeads - 1 <= (page - 1) * limit) {
        setPage((current) => Math.max(1, current - 1));
      }
      setTimeout(() => {
        setSuccessMessage(null);
      }, 4000);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, 'Failed to delete lead. Please try again.'));
    }
  };

  const handleOpenModal = () => {
    setEditingLead(null);
    setErrorMessage(null);
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (lead: Lead) => {
    setEditingLead(lead);
    setErrorMessage(null);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingLead(null);
  };

  // Define Columns for Reusable DataTable
  const columns: DataTableColumn<Lead>[] = useMemo(
    () => [
      {
        id: 'name',
        header: 'Name & Title',
        className: 'min-w-[180px]',
        cell: (item: Lead) => (
          <div>
            <span className="block text-table font-bold text-slate-900">{item.contact_name}</span>
            <span className="text-caption font-medium text-slate-600">{item.title}</span>
          </div>
        ),
      },
      {
        id: 'company',
        header: 'Company',
        className: 'min-w-[150px]',
        cell: (item: Lead) => (
          <div className="flex items-center gap-1.5 text-table font-medium text-slate-900">
            <Building2 className="w-3.5 h-3.5 text-slate-400 shrink-0" />
            <span className="truncate">{item.company}</span>
          </div>
        ),
      },
      {
        id: 'contact',
        header: 'Email / Phone',
        className: 'min-w-[180px]',
        cell: (item: Lead) => (
          <div className="text-table font-medium text-slate-900 space-y-0.5">
            <div className="flex items-center gap-1.5">
              <Mail className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
              <span className="truncate">{item.email}</span>
            </div>
            {item.phone && (
              <div className="flex items-center gap-1.5 text-caption text-slate-600">
                <Phone className="w-3 h-3 shrink-0" />
                <span>{item.phone}</span>
              </div>
            )}
          </div>
        ),
      },
      {
        id: 'source',
        header: 'Source',
        className: 'min-w-[100px]',
        cell: (item: Lead) => {
          const formattedSource = formatLeadSource(item.source);
          return (
            <span className="text-table font-medium text-slate-800" title={formattedSource !== item.source ? item.source : undefined}>
              {formattedSource}
            </span>
          );
        },
      },
      {
        id: 'status',
        header: 'Status',
        className: 'min-w-[110px]',
        cell: (item: Lead) => {
          const canonicalStatus = canonicalLeadStatus(item.status);
          const label = (canonicalStatus ?? item.status.trim()) || 'Unknown';
          const statusStyle = canonicalStatus
            ? STATUS_STYLES[canonicalStatus]
            : 'bg-slate-100 text-slate-800 border-slate-200';
          return (
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-badge font-semibold border ${statusStyle}`}>
              <span className="w-1.5 h-1.5 rounded-full bg-current mr-1.5" />
              {label}
            </span>
          );
        },
      },
      {
        id: 'score',
        header: 'AI Score',
        className: 'min-w-[100px] text-right',
        cell: (item: Lead) => (
          <div className="text-right">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-purple-50 text-purple-800 border border-purple-200 text-badge font-semibold">
              <Sparkles className="w-3 h-3 text-purple-600" />
              {item.score ?? 75}/100
            </span>
          </div>
        ),
      },
    ],
    []
  );

  const handleArchiveLead = async (lead: Lead) => {
    try {
      await archiveLeadMutation.mutateAsync(lead.id);
      setSuccessMessage(`Lead "${lead.contact_name}" archived successfully!`);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, 'Failed to archive lead.'));
    }
  };

  const handleUnarchiveLead = async (lead: Lead) => {
    try {
      await unarchiveLeadMutation.mutateAsync(lead.id);
      setSuccessMessage(`Lead "${lead.contact_name}" unarchived/restored successfully!`);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, 'Failed to unarchive lead.'));
    }
  };

  const handleConfirmAssign = async () => {
    if (!assigningLead) return;
    try {
      await assignLeadMutation.mutateAsync({ leadId: assigningLead.id, userId: selectedUserId });
      setSuccessMessage(`Lead "${assigningLead.contact_name}" assigned successfully!`);
      setAssigningLead(null);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (error: unknown) {
      setErrorMessage(getErrorMessage(error, 'Failed to assign lead.'));
    }
  };

  // Define Row Actions for DataTable dynamically based on Lead state
  const actions = (lead: Lead): TableActionOption<Lead>[] => [
    {
      label: 'Edit Lead',
      permission: PERMISSIONS.LEADS.UPDATE,
      icon: <Pencil className="w-3.5 h-3.5 mr-2 text-slate-500" />,
      onClick: (item) => handleOpenEditModal(item),
    },
    {
      label: 'Assign Lead',
      permission: PERMISSIONS.LEADS.ASSIGN,
      icon: <UserCheck className="w-3.5 h-3.5 mr-2 text-indigo-600" />,
      onClick: (item) => {
        setAssigningLead(item);
        setSelectedUserId(item.assigned_to || (users[0]?.id ?? ''));
      },
    },
    ...(lead.is_archived
      ? [
          {
            label: 'Unarchive Lead',
            permission: PERMISSIONS.LEADS.UPDATE,
            icon: <RotateCcw className="w-3.5 h-3.5 mr-2 text-emerald-600" />,
            onClick: (item: Lead) => handleUnarchiveLead(item),
          },
        ]
      : [
          {
            label: 'Archive Lead',
            permission: PERMISSIONS.LEADS.UPDATE,
            icon: <Archive className="w-3.5 h-3.5 mr-2 text-amber-600" />,
            onClick: (item: Lead) => handleArchiveLead(item),
          },
        ]),
    {
      label: 'Delete Lead',
      variant: 'destructive',
      permission: PERMISSIONS.LEADS.DELETE,
      icon: <Trash2 className="w-3.5 h-3.5 mr-2 text-rose-600" />,
      onClick: (item) => {
        setErrorMessage(null);
        setLeadToDelete(item);
      },
    },
  ];

  return (
    <div className="space-y-6 text-black">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4 border-b border-[#E5E7EB]">
        <div>
          <h1 className="text-page-title">
            Lead Management
          </h1>
          <p className="text-caption mt-1">
            Capture, track, and score sales leads with AI
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* Bulk Actions Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button type="button" variant="outline" className="w-full gap-2 text-button font-medium sm:w-auto">
              <Sliders className="w-4 h-4 text-[#2563EB]" />
              <span>Bulk Actions</span>
              {selectedIds.size > 0 && (
                <span className="ml-1 px-2 py-0.5 rounded-full bg-[#2563EB] text-white text-badge font-semibold">
                  {selectedIds.size}
                </span>
              )}
              <ChevronDown className="w-4 h-4 text-[#9CA3AF]" />
            </Button>
              </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuLabel className="text-badge font-semibold text-[#111827]">
                {selectedIds.size > 0 ? `Bulk Actions (${selectedIds.size} selected)` : 'Select leads below to apply'}
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <PermissionGate permission={PERMISSIONS.LEADS.BULK_UPDATE}>
                <DropdownMenuItem
                  disabled={selectedIds.size === 0 || bulkArchiveMutation.isPending}
                  onClick={handleBulkArchive}
                  className={`cursor-pointer text-button font-medium ${selectedIds.size === 0 ? 'opacity-50 cursor-not-allowed' : 'text-[#374151] hover:bg-[#F3F4F6]'}`}
                >
                  <Archive className="w-4 h-4 mr-2 text-[#F59E0B]" />
                  <span>Bulk Archive ({selectedIds.size})</span>
                </DropdownMenuItem>
              </PermissionGate>
              <DropdownMenuSeparator />
              <PermissionGate permission={PERMISSIONS.LEADS.BULK_DELETE}>
                <DropdownMenuItem
                  variant="destructive"
                  disabled={selectedIds.size === 0 || bulkDeleteMutation.isPending}
                  onSelect={() => {
                    setErrorMessage(null);
                    setBulkDeleteIds(Array.from(selectedIds));
                  }}
                  className={`cursor-pointer text-button font-medium ${selectedIds.size === 0 ? 'opacity-50 cursor-not-allowed' : 'text-[#DC2626] hover:bg-[#DC2626]/10'}`}
                >
                  <Trash2 className="w-4 h-4 mr-2 text-[#DC2626]" />
                  <span>Bulk Delete ({selectedIds.size})</span>
                </DropdownMenuItem>
              </PermissionGate>
            </DropdownMenuContent>
          </DropdownMenu>

          <PermissionGate permission={PERMISSIONS.LEADS.CREATE}>
            <Button
              type="button"
              onClick={handleOpenModal}
              size="default"
              variant="primary"
              className="shadow-saas-sm px-4 text-button cursor-pointer"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add New Lead
            </Button>
          </PermissionGate>
        </div>
      </div>

      {/* Success Notification Alert */}
      {successMessage && (
        <Alert variant="default" className="bg-emerald-50 border-emerald-300 text-emerald-950 font-bold">
          <CheckCircle2 className="h-4 w-4 text-emerald-600 mr-2" />
          <AlertDescription className="text-emerald-900 font-bold">
            {successMessage}
          </AlertDescription>
        </Alert>
      )}

      {(errorMessage || isError) && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="flex flex-wrap items-center justify-between gap-3 text-rose-900">
            <span>
              {errorMessage || (leadsError instanceof Error ? leadsError.message : 'Failed to load leads.')}
            </span>
            {isError && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => refetch()}
                disabled={isLoading}
                className="border-rose-300 bg-white text-rose-800 hover:bg-rose-100"
              >
                Try Again
              </Button>
            )}
          </AlertDescription>
        </Alert>
      )}

      {/* Reusable Enterprise DataTable Component */}
      <DataTable<Lead>
        columns={columns}
        data={leads}
        getRowKey={(item) => item.id}
        emptyTitle="No leads found"
        emptyDescription="Click '+ Add New Lead' above to create your first sales lead."
        onRowClick={(lead) => router.push(`/leads/${lead.id}`)}
        showCheckbox
        selectedIds={selectedIds}
        onToggleRow={handleToggleRow}
        onToggleAllRows={handleToggleAllRows}
        getSelectionLabel={(lead) => `Select ${lead.contact_name}`}
        showAvatar
        getAvatarData={(item) => ({ name: item.contact_name, color: '#4f46e5' })}
        actionVariant="menu"
        actions={actions}
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search lead, company..."
        statusFilter={{
          value: statusFilter,
          options: [
            { label: 'All statuses', value: '' },
            ...LEAD_STATUS_OPTIONS.map((leadStatus) => ({ label: leadStatus, value: leadStatus })),
          ],
          onChange: (value) => {
            setStatusFilter(value);
            setPage(1);
            setSelectedIds(new Set());
          },
        }}
        isLoading={isLoading}
        pagination={{
          pageIndex: page - 1,
          pageCount: Math.max(1, Math.ceil(totalLeads / limit)),
          onPageChange: (nextPage) => {
            setPage(nextPage + 1);
            setSelectedIds(new Set());
          },
          totalRecords: totalLeads,
        }}
        toolbarActions={
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isLoading}
            aria-label="Refresh leads"
            className="border-slate-300 text-slate-900 font-bold hover:bg-slate-100 text-xs h-9"
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        }
      />

      {isModalOpen && (
        <LeadFormDialog
          isOpen={isModalOpen}
          onClose={handleCloseModal}
          lead={editingLead}
          onSaved={(savedLead, mode) => {
            setIsModalOpen(false);
            setEditingLead(null);
            setSuccessMessage(
              mode === 'created'
                ? `Lead for "${savedLead.contact_name}" created successfully!`
                : `Lead "${savedLead.contact_name}" updated successfully!`,
            );
            window.setTimeout(() => setSuccessMessage(null), 4000);
          }}
        />
      )}

      <ConfirmModal
        isOpen={!!leadToDelete}
        onClose={() => {
          if (!deleteLeadMutation.isPending) setLeadToDelete(null);
        }}
        onConfirm={handleConfirmDelete}
        title="Delete Sales Lead"
        description="This permanently removes the lead and cannot be undone."
        confirmText="Delete Lead"
        variant="danger"
        isLoading={deleteLeadMutation.isPending}
        message={
          leadToDelete && (
            <div className="space-y-3">
              <p>
                Delete <strong className="text-slate-900">{leadToDelete.contact_name}</strong> from{' '}
                <strong className="text-slate-900">{leadToDelete.company}</strong>?
              </p>
              {errorMessage && <p className="font-semibold text-rose-700">{errorMessage}</p>}
            </div>
          )
        }
      />

      <ConfirmModal
        isOpen={bulkDeleteIds !== null}
        onClose={() => {
          if (!bulkDeleteMutation.isPending) setBulkDeleteIds(null);
        }}
        onConfirm={handleConfirmBulkDelete}
        title={`Delete ${bulkDeleteIds?.length ?? 0} Leads`}
        description="This bulk action cannot be undone."
        confirmText={`Delete ${bulkDeleteIds?.length ?? 0} Leads`}
        variant="danger"
        isLoading={bulkDeleteMutation.isPending}
        message={
          <div className="space-y-3">
            <p>
              Permanently delete all <strong className="text-slate-900">{bulkDeleteIds?.length ?? 0}</strong>{' '}
              selected leads?
            </p>
            {errorMessage && <p className="font-semibold text-rose-700">{errorMessage}</p>}
          </div>
        }
      />

      {/* ASSIGN LEAD MODAL DIALOG */}
      {assigningLead && (
        <ModalShell
          isOpen={!!assigningLead}
          onClose={() => setAssigningLead(null)}
          size="md"
          title={
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shrink-0">
                <UserCheck className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <h3 className="text-base font-black text-indigo-950 break-words">Assign Sales Lead</h3>
                <p className="text-xs font-bold text-indigo-700 break-words">Assign to team member / sales rep</p>
              </div>
            </div>
          }
        >
          {/* Modal Content */}
          <div className="space-y-4">
            <p className="text-xs font-bold text-slate-700 leading-relaxed">
              Assign sales lead <span className="font-black text-slate-950">&ldquo;{assigningLead.contact_name}&rdquo;</span> ({assigningLead.company}) to a team member:
            </p>

            <div className="space-y-2">
              <Label className="text-xs font-black text-black">Select Sales Rep / User</Label>

              {/* Quick Search Input */}
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  type="text"
                  placeholder="Search user by name, email, or role..."
                  value={userSearchTerm}
                  onChange={(e) => setUserSearchTerm(e.target.value)}
                  className="pl-9 text-xs h-9 bg-slate-50 border-slate-300 font-bold text-black focus:bg-white"
                />
                {userSearchTerm && (
                  <button
                    type="button"
                    onClick={() => setUserSearchTerm('')}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700 p-0.5 cursor-pointer"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              {/* Searchable User Selection List */}
              <div className="max-h-44 overflow-y-auto border border-slate-200 rounded-xl bg-slate-50 p-1.5 space-y-1">
                <button
                  type="button"
                  onClick={() => setSelectedUserId('')}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-bold transition-all text-left cursor-pointer ${
                    selectedUserId === ''
                      ? 'bg-indigo-600 text-white font-black shadow-xs'
                      : 'text-slate-700 hover:bg-slate-200/70'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-black ${selectedUserId === '' ? 'bg-white/20 text-white' : 'bg-slate-300 text-slate-700'}`}>
                      <User className="h-3.5 w-3.5" aria-hidden="true" />
                    </div>
                    <span>Unassigned (No Owner)</span>
                  </div>
                  {selectedUserId === '' && <CheckCircle2 className="w-4 h-4 text-white" />}
                </button>

                {users.length === 0 ? (
                  <div className="p-3 text-center text-xs font-bold text-slate-500">
                    No team members match &ldquo;{userSearchTerm}&rdquo;
                  </div>
                ) : (
                  users.map((u) => {
                    const isSelected = selectedUserId === u.id;
                    return (
                      <button
                        key={u.id}
                        type="button"
                        onClick={() => setSelectedUserId(u.id)}
                        className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-all text-left cursor-pointer ${
                          isSelected
                            ? 'bg-indigo-600 text-white font-black shadow-xs'
                            : 'text-slate-900 hover:bg-slate-200/70 font-bold'
                        }`}
                      >
                        <div className="flex items-center gap-2.5 min-w-0">
                          <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-black shrink-0 ${isSelected ? 'bg-white text-indigo-700' : 'bg-indigo-100 text-indigo-700'}`}>
                            {u.name ? u.name.charAt(0).toUpperCase() : 'U'}
                          </div>
                          <div className="min-w-0">
                            <div className="font-black truncate">{u.name}</div>
                            <div className={`text-[10px] truncate ${isSelected ? 'text-indigo-100 font-bold' : 'text-slate-700'}`}>
                              {u.email}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0 ml-2">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-black ${
                            isSelected 
                              ? 'bg-white/20 text-white' 
                              : 'bg-slate-200 text-slate-800'
                          }`}>
                            {u.role || 'Sales Rep'}
                          </span>
                          {isSelected && <CheckCircle2 className="w-4 h-4 text-white" />}
                        </div>
                      </button>
                    );
                  })
                )}
              </div>

              {/* Dropdown Select Menu */}
              <div className="pt-1">
                <ResponsiveSelect
                  value={selectedUserId}
                  onValueChange={setSelectedUserId}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-white text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
                >
                  <option value="">Unassigned (No Owner)</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.name} ({u.role || 'Sales Rep'}) - {u.email}
                    </option>
                  ))}
                </ResponsiveSelect>
              </div>
            </div>

            {/* Modal Actions */}
            <div className="pt-2 flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 border-t border-slate-200">
              <Button
                type="button"
                variant="outline"
                onClick={() => setAssigningLead(null)}
                disabled={assignLeadMutation.isPending}
                className="border-slate-300 text-black font-bold hover:bg-slate-100 text-xs"
              >
                Cancel
              </Button>
              <Button
                type="button"
                onClick={handleConfirmAssign}
                disabled={assignLeadMutation.isPending}
                className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold shadow-sm text-xs px-5"
              >
                {assignLeadMutation.isPending ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                    Assigning...
                  </>
                ) : (
                  'Assign Lead'
                )}
              </Button>
            </div>
          </div>
        </ModalShell>
      )}
    </div>
  );
}
