'use client';

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
  MapPin,
  Sliders,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Archive,
  UserCheck,
  RotateCcw,
  Search
} from 'lucide-react';
import { 
  Button, 
  Card, 
  Label, 
  Input, 
  Badge, 
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
import { PermissionGate } from '@/components/common/permission-gate';
import { PERMISSIONS } from '@/lib/permissions';
import { 
  useLeadsQuery, 
  useCreateLeadMutation, 
  useUpdateLeadMutation, 
  useDeleteLeadMutation, 
  useBulkDeleteLeadsMutation,
  useBulkArchiveLeadsMutation,
  useArchiveLeadMutation,
  useUnarchiveLeadMutation,
  useAssignLeadMutation,
  Lead 
} from '@/lib/api/leads';
import { useOrganizationsQuery } from '@/lib/api/organizations';
import { useCompaniesQuery } from '@/lib/api/companies';
import { useUsersQuery } from '@/lib/api/users';

export default function LeadsPage() {
  const router = useRouter();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingLead, setEditingLead] = useState<Lead | null>(null);
  const [leadToDelete, setLeadToDelete] = useState<Lead | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [page, setPage] = useState(1);
  const limit = 15;
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Debounce search input to avoid refetching API on every single character typed
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
      setPage(1);
    }, 250);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Modal Category Tab State
  const [activeModalTab, setActiveModalTab] = useState<'contact' | 'company' | 'location' | 'organization'>('contact');
  
  // Form State
  const [contactName, setContactName] = useState('');
  const [company, setCompany] = useState('');
  const [customCompany, setCustomCompany] = useState('');
  const [title, setTitle] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [website, setWebsite] = useState('');
  const [industry, setIndustry] = useState('');
  const [companySize, setCompanySize] = useState('');
  const [country, setCountry] = useState('');
  const [stateName, setStateName] = useState('');
  const [city, setCity] = useState('');
  const [address, setAddress] = useState('');
  const [postalCode, setPostalCode] = useState('');
  const [status, setStatus] = useState('New');
  const [source, setSource] = useState('Website');
  const [organizationId, setOrganizationId] = useState('');
  const [score, setScore] = useState<number>(75);
  const [assignedTo, setAssignedTo] = useState<string>('');
  const [isArchived, setIsArchived] = useState<boolean>(false);

  // Feedback Banner State
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // TanStack Query Hooks for Leads, Organizations, Companies & Users API
  const { data: leads = [], isLoading, isError, refetch } = useLeadsQuery({
    page,
    limit,
    search: debouncedSearchTerm || undefined,
    status: statusFilter || undefined,
  });

  const [userSearchTerm, setUserSearchTerm] = useState<string>('');
  const [debouncedUserSearchTerm, setDebouncedUserSearchTerm] = useState<string>('');

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedUserSearchTerm(userSearchTerm);
    }, 250);
    return () => clearTimeout(timer);
  }, [userSearchTerm]);

  const { data: organizations = [], isLoading: isOrgsLoading } = useOrganizationsQuery();
  const { data: companies = [], isLoading: isCompaniesLoading } = useCompaniesQuery();
  const { data: users = [], isLoading: isUsersLoading } = useUsersQuery(1, 100, debouncedUserSearchTerm || undefined);

  // Auto-set initial organization ID when organizations data is loaded from API
  useEffect(() => {
    if (organizations.length > 0 && !organizationId) {
      setOrganizationId(organizations[0].id);
    }
  }, [organizations, organizationId]);

  const [assigningLead, setAssigningLead] = useState<Lead | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<string>('');

  const createLeadMutation = useCreateLeadMutation();
  const updateLeadMutation = useUpdateLeadMutation();
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
    if (checked) {
      setSelectedIds(new Set(leads.map((l) => l.id)));
    } else {
      setSelectedIds(new Set());
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    try {
      const ids = Array.from(selectedIds);
      await bulkDeleteMutation.mutateAsync(ids);
      setSuccessMessage(`Successfully deleted ${ids.length} selected lead(s)!`);
      setSelectedIds(new Set());
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Bulk delete failed. Please try again.');
    }
  };

  const handleBulkArchive = async () => {
    if (selectedIds.size === 0) return;
    try {
      const ids = Array.from(selectedIds);
      await bulkArchiveMutation.mutateAsync(ids);
      setSuccessMessage(`Successfully archived ${ids.length} selected lead(s)!`);
      setSelectedIds(new Set());
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Bulk archive failed. Please try again.');
    }
  };

  const handleConfirmDelete = async () => {
    if (!leadToDelete) return;
    try {
      await deleteLeadMutation.mutateAsync(leadToDelete.id);
      setSuccessMessage(`Lead "${leadToDelete.contact_name}" deleted successfully!`);
      setLeadToDelete(null);
      setTimeout(() => {
        setSuccessMessage(null);
      }, 4000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to delete lead. Please try again.');
    }
  };

  const resetForm = () => {
    setEditingLead(null);
    setActiveModalTab('contact');
    setContactName('');
    setCompany(companies.length > 0 ? companies[0].name : '');
    setCustomCompany('');
    setTitle('');
    setEmail('');
    setPhone('');
    setWebsite('');
    setIndustry('');
    setCompanySize('');
    setCountry('');
    setStateName('');
    setCity('');
    setAddress('');
    setPostalCode('');
    setStatus('New');
    setSource('Website');
    setOrganizationId(organizations.length > 0 ? organizations[0].id : 'org-1');
    setScore(75);
    setAssignedTo('');
    setIsArchived(false);
    setErrorMessage(null);
  };

  const handleAutofill = () => {
    setContactName("Alex Morgan");
    setCompany(companies.length > 0 ? companies[0].name : "Nexus Tech Solutions");
    setTitle("Vice President of Enterprise Sales");
    setEmail("alex.morgan@nexustech.com");
    setPhone("+1 (555) 234-5678");
    setWebsite("https://nexustech.com");
    setIndustry("Software & Cloud Services");
    setCompanySize("51-200");
    setCountry("United States");
    setStateName("CA");
    setCity("San Francisco");
    setAddress("100 Technology Way, Suite 400");
    setPostalCode("94107");
    setStatus("Qualified");
    setSource("LinkedIn");
    if (organizations.length > 0) setOrganizationId(organizations[0].id);
    setScore(88);
    if (users.length > 0) setAssignedTo(users[0].id);
    setIsArchived(false);
    setErrorMessage(null);
  };

  const handleOpenModal = () => {
    resetForm();
    setActiveModalTab('contact');
    if (organizations.length > 0) setOrganizationId(organizations[0].id);
    if (companies.length > 0) setCompany(companies[0].name);
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (lead: Lead) => {
    setEditingLead(lead);
    setActiveModalTab('contact');
    setContactName(lead.contact_name || '');
    setCompany(lead.company || '');
    setCustomCompany('');
    setTitle(lead.title || '');
    setEmail(lead.email || '');
    setPhone(lead.phone || '');
    setWebsite(lead.website || '');
    setIndustry(lead.industry || '');
    setCompanySize(lead.company_size || '');
    setCountry(lead.country || '');
    setStateName(lead.state || '');
    setCity(lead.city || '');
    setAddress(lead.address || '');
    setPostalCode(lead.postal_code || '');
    setStatus(lead.status || 'New');
    setSource(lead.source || 'Website');
    setOrganizationId(lead.organization_id || (organizations[0]?.id ?? 'org-1'));
    setScore(lead.score ?? 75);
    setAssignedTo(lead.assigned_to || '');
    setIsArchived(lead.is_archived ?? false);
    setErrorMessage(null);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    if (createLeadMutation.isPending || updateLeadMutation.isPending) return;
    setIsModalOpen(false);
    resetForm();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);

    const finalCompany = company === 'other' ? customCompany.trim() : company.trim();

    if (!contactName.trim() || !email.trim()) {
      setActiveModalTab('contact');
      setErrorMessage('Contact Name and Email are required.');
      return;
    }

    if (!finalCompany) {
      setActiveModalTab('company');
      setErrorMessage('Company Name is required.');
      return;
    }

    try {
      const payload = {
        contact_name: contactName.trim(),
        company: finalCompany,
        title: title.trim() || `${contactName.trim()} Opportunity`,
        email: email.trim(),
        phone: phone.trim() || undefined,
        website: website.trim() || undefined,
        industry: industry.trim() || undefined,
        company_size: companySize || undefined,
        country: country.trim() || undefined,
        state: stateName.trim() || undefined,
        city: city.trim() || undefined,
        address: address.trim() || undefined,
        postal_code: postalCode.trim() || undefined,
        status,
        source,
        score: Number(score) || 75,
        assigned_to: assignedTo.trim() || undefined,
        is_archived: isArchived,
        organization_id: organizationId || (organizations[0]?.id ?? 'org-1'),
      };

      if (editingLead) {
        await updateLeadMutation.mutateAsync({ id: editingLead.id, payload });
        setSuccessMessage(`Lead "${contactName}" updated successfully!`);
      } else {
        await createLeadMutation.mutateAsync(payload);
        setSuccessMessage(`Lead for "${contactName}" created successfully!`);
      }

      setIsModalOpen(false);
      resetForm();

      setTimeout(() => {
        setSuccessMessage(null);
      }, 4000);
    } catch (err: any) {
      setErrorMessage(err?.message || `Failed to ${editingLead ? 'update' : 'create'} lead. Please check API server.`);
    }
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
            <span className="block text-xs font-black text-slate-900">{item.contact_name}</span>
            <span className="text-[11px] font-semibold text-slate-500">{item.title}</span>
          </div>
        ),
      },
      {
        id: 'company',
        header: 'Company',
        className: 'min-w-[150px]',
        cell: (item: Lead) => (
          <div className="flex items-center gap-1.5 font-bold text-xs text-slate-900">
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
          <div className="text-xs font-bold text-slate-900 space-y-0.5">
            <div className="flex items-center gap-1.5">
              <Mail className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
              <span className="truncate">{item.email}</span>
            </div>
            {item.phone && (
              <div className="flex items-center gap-1.5 text-slate-500 text-[11px]">
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
        cell: (item: Lead) => (
          <span className="text-xs font-bold text-slate-800">{item.source}</span>
        ),
      },
      {
        id: 'status',
        header: 'Status',
        className: 'min-w-[110px]',
        cell: (item: Lead) => (
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-black border ${
            item.status === 'New' ? 'bg-blue-50 text-blue-800 border-blue-200' :
            item.status === 'Qualified' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' :
            item.status === 'Contacted' ? 'bg-amber-50 text-amber-800 border-amber-200' :
            'bg-slate-100 text-slate-800 border-slate-200'
          }`}>
            <span className="w-1.5 h-1.5 rounded-full bg-current mr-1.5" />
            {item.status}
          </span>
        ),
      },
      {
        id: 'score',
        header: 'AI Score',
        className: 'min-w-[100px] text-right',
        cell: (item: Lead) => (
          <div className="text-right">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-purple-50 text-purple-800 border border-purple-200 text-[11px] font-black">
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
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to archive lead.');
    }
  };

  const handleUnarchiveLead = async (lead: Lead) => {
    try {
      await unarchiveLeadMutation.mutateAsync(lead.id);
      setSuccessMessage(`Lead "${lead.contact_name}" unarchived/restored successfully!`);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to unarchive lead.');
    }
  };

  const handleConfirmAssign = async () => {
    if (!assigningLead) return;
    try {
      await assignLeadMutation.mutateAsync({ leadId: assigningLead.id, userId: selectedUserId });
      setSuccessMessage(`Lead "${assigningLead.contact_name}" assigned successfully!`);
      setAssigningLead(null);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to assign lead.');
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
      onClick: (item) => setLeadToDelete(item),
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
            <DropdownMenuTrigger className="h-10 px-4 border border-[#E5E7EB] bg-white hover:bg-[#F9FAFB] text-[#374151] font-medium rounded-btn text-button inline-flex items-center gap-2 cursor-pointer shadow-saas-sm">
              <Sliders className="w-4 h-4 text-[#2563EB]" />
              <span>Bulk Actions</span>
              {selectedIds.size > 0 && (
                <span className="ml-1 px-2 py-0.5 rounded-full bg-[#2563EB] text-white text-badge font-semibold">
                  {selectedIds.size}
                </span>
              )}
              <ChevronDown className="w-4 h-4 text-[#9CA3AF]" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuLabel className="text-badge font-semibold text-[#111827]">
                {selectedIds.size > 0 ? `Bulk Actions (${selectedIds.size} selected)` : 'Select leads below to apply'}
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <PermissionGate permission={PERMISSIONS.LEADS.BULK_UPDATE}>
                <DropdownMenuItem
                  disabled={selectedIds.size === 0}
                  onClick={handleBulkArchive}
                  className={`cursor-pointer text-button font-medium ${selectedIds.size === 0 ? 'opacity-50 cursor-not-allowed' : 'text-[#374151] hover:bg-[#F3F4F6]'}`}
                >
                  <Archive className="w-4 h-4 mr-2 text-[#F59E0B]" />
                  <span>Bulk Archive ({selectedIds.size})</span>
                </DropdownMenuItem>
              </PermissionGate>
              <PermissionGate permission={PERMISSIONS.LEADS.BULK_DELETE}>
                <DropdownMenuItem
                  disabled={selectedIds.size === 0}
                  onClick={handleBulkDelete}
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
              + Add New Lead
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
        showAvatar
        getAvatarData={(item) => ({ name: item.contact_name, color: '#4f46e5' })}
        actionVariant="menu"
        actions={actions}
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search lead, company..."
        isLoading={isLoading}
        pagination={{
          pageIndex: page - 1,
          pageCount: leads.length >= limit ? page + 1 : page,
          onPageChange: (p) => setPage(p + 1),
          totalRecords: (page - 1) * limit + leads.length,
        }}
        toolbarActions={
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            className="border-slate-300 text-slate-900 font-bold hover:bg-slate-100 text-xs h-9"
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        }
      />

      {/* CREATE / EDIT LEAD MODAL DIALOG */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-3xl xl:max-w-4xl bg-white rounded-2xl border border-slate-300 shadow-2xl overflow-hidden text-black flex flex-col transition-all duration-200">
            {/* Modal Header */}
            <div className="p-5 sm:p-6 border-b border-slate-200 bg-slate-50 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center text-white shadow-sm">
                  {editingLead ? <Pencil className="w-4 h-4" /> : <Plus className="w-5 h-5" />}
                </div>
                <div>
                  <h3 className="text-lg sm:text-xl font-black text-black">
                    {editingLead ? 'Edit Sales Lead' : 'Create New Sales Lead'}
                  </h3>
                  <p className="text-xs font-bold text-slate-700">
                    {editingLead ? `Update details for ${editingLead.contact_name}` : 'Fill lead, company & location details below'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleAutofill}
                  className="border-indigo-200 bg-indigo-50/90 hover:bg-indigo-100 text-indigo-700 font-black text-xs shadow-2xs gap-1.5 cursor-pointer px-3 py-1.5"
                >
                  <Sparkles className="w-3.5 h-3.5 text-indigo-600 animate-pulse" />
                  <span>Auto-fill Sample Data</span>
                </Button>
                <button
                  type="button"
                  onClick={handleCloseModal}
                  className="p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-200 transition cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Category Navigation Tabs */}
            <div className="flex items-center border-b border-slate-200 bg-slate-100/70 px-4 sm:px-6 pt-2.5 gap-1.5 overflow-x-auto shrink-0 select-none">
              <button
                type="button"
                onClick={() => setActiveModalTab('contact')}
                className={`flex items-center gap-2 px-4 py-2.5 text-xs sm:text-sm font-bold rounded-t-xl transition-all border-b-2 cursor-pointer ${
                  activeModalTab === 'contact'
                    ? 'bg-white text-indigo-600 border-indigo-600 shadow-xs font-black'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60 border-transparent'
                }`}
              >
                <User className="w-4 h-4" />
                <span>1. Contact Info</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveModalTab('company')}
                className={`flex items-center gap-2 px-4 py-2.5 text-xs sm:text-sm font-bold rounded-t-xl transition-all border-b-2 cursor-pointer ${
                  activeModalTab === 'company'
                    ? 'bg-white text-indigo-600 border-indigo-600 shadow-xs font-black'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60 border-transparent'
                }`}
              >
                <Building2 className="w-4 h-4" />
                <span>2. Company Details</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveModalTab('location')}
                className={`flex items-center gap-2 px-4 py-2.5 text-xs sm:text-sm font-bold rounded-t-xl transition-all border-b-2 cursor-pointer ${
                  activeModalTab === 'location'
                    ? 'bg-white text-indigo-600 border-indigo-600 shadow-xs font-black'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60 border-transparent'
                }`}
              >
                <MapPin className="w-4 h-4" />
                <span>3. Address & Location</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveModalTab('organization')}
                className={`flex items-center gap-2 px-4 py-2.5 text-xs sm:text-sm font-bold rounded-t-xl transition-all border-b-2 cursor-pointer ${
                  activeModalTab === 'organization'
                    ? 'bg-white text-indigo-600 border-indigo-600 shadow-xs font-black'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60 border-transparent'
                }`}
              >
                <Sliders className="w-4 h-4" />
                <span>4. Status & Organization</span>
              </button>
            </div>

            {/* Modal Form Body */}
            <form onSubmit={handleSubmit} className="p-6 sm:p-7 space-y-6 overflow-y-auto max-h-[calc(85vh-150px)]">
              {errorMessage && (
                <Alert variant="destructive" className="bg-rose-50 border-rose-300 text-rose-950 font-bold">
                  <AlertCircle className="h-4 w-4 text-rose-600 mr-2" />
                  <AlertDescription className="text-rose-900 font-bold text-xs">
                    {errorMessage}
                  </AlertDescription>
                </Alert>
              )}

              {/* TAB 1: Contact Information */}
              {activeModalTab === 'contact' && (
                <div className="space-y-4 animate-in fade-in-50">
                  <h4 className="text-xs font-black uppercase tracking-wider text-indigo-700 pb-1 border-b border-slate-200 flex items-center gap-1.5">
                    <User className="w-4 h-4" />
                    1. Contact Information
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">Contact Name *</Label>
                      <Input
                        type="text"
                        required
                        placeholder="e.g. John Doe"
                        value={contactName}
                        onChange={(e) => setContactName(e.target.value)}
                        className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">Email Address *</Label>
                      <Input
                        type="email"
                        required
                        placeholder="john@acmecorp.com"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">Phone Number</Label>
                      <Input
                        type="tel"
                        placeholder="+1 (555) 000-0000"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">Opportunity / Lead Title</Label>
                      <Input
                        type="text"
                        placeholder="e.g. Enterprise Cloud Deal"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: Company Information */}
              {activeModalTab === 'company' && (
                <div className="space-y-4 animate-in fade-in-50">
                  <h4 className="text-xs font-black uppercase tracking-wider text-indigo-700 pb-1 border-b border-slate-200 flex items-center gap-1.5">
                    <Building2 className="w-4 h-4" />
                    2. Company & Industry Details
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">Select Company *</Label>
                      <select
                        value={company}
                        onChange={(e) => setCompany(e.target.value)}
                        className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      >
                        {isCompaniesLoading ? (
                          <option value="">Loading companies...</option>
                        ) : (
                          companies.map((c) => (
                            <option key={c.id} value={c.name}>
                              {c.name}
                            </option>
                          ))
                        )}
                        <option value="other">+ Enter Custom Company...</option>
                      </select>
                    </div>

                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">Website</Label>
                      <Input
                        type="url"
                        placeholder="https://company.com"
                        value={website}
                        onChange={(e) => setWebsite(e.target.value)}
                        className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                      />
                    </div>
                  </div>

                  {company === 'other' && (
                    <div className="space-y-1.5 animate-in fade-in-50">
                      <Label className="text-xs font-black text-black">Custom Company Name *</Label>
                      <Input
                        type="text"
                        required
                        placeholder="Enter new company name..."
                        value={customCompany}
                        onChange={(e) => setCustomCompany(e.target.value)}
                        className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                      />
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">Industry</Label>
                      <Input
                        type="text"
                        placeholder="e.g. Software, Finance, Healthcare"
                        value={industry}
                        onChange={(e) => setIndustry(e.target.value)}
                        className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">Company Size</Label>
                      <select
                        value={companySize}
                        onChange={(e) => setCompanySize(e.target.value)}
                        className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="">Select Company Size...</option>
                        <option value="1-10">1-10 Employees</option>
                        <option value="11-50">11-50 Employees</option>
                        <option value="51-200">51-200 Employees</option>
                        <option value="201-500">201-500 Employees</option>
                        <option value="500+">500+ Employees</option>
                      </select>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 3: Location & Address Details */}
              {activeModalTab === 'location' && (
                <div className="space-y-4 animate-in fade-in-50">
                  <h4 className="text-xs font-black uppercase tracking-wider text-indigo-700 pb-1 border-b border-slate-200 flex items-center gap-1.5">
                    <MapPin className="w-4 h-4" />
                    3. Address & Location
                  </h4>
                  <div className="space-y-1.5">
                    <Label className="text-xs font-black text-black">Address</Label>
                    <Input
                      type="text"
                      placeholder="Street address, suite, or building"
                      value={address}
                      onChange={(e) => setAddress(e.target.value)}
                      className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                    />
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">City</Label>
                      <Input
                        type="text"
                        placeholder="e.g. Chennai"
                        value={city}
                        onChange={(e) => setCity(e.target.value)}
                        className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">State</Label>
                      <Input
                        type="text"
                        placeholder="e.g. TN"
                        value={stateName}
                        onChange={(e) => setStateName(e.target.value)}
                        className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">Country</Label>
                      <Input
                        type="text"
                        placeholder="e.g. India"
                        value={country}
                        onChange={(e) => setCountry(e.target.value)}
                        className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">Postal Code</Label>
                      <Input
                        type="text"
                        placeholder="600096"
                        value={postalCode}
                        onChange={(e) => setPostalCode(e.target.value)}
                        className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 4: Status, Source, Score & Organization */}
              {activeModalTab === 'organization' && (
                <div className="space-y-4 animate-in fade-in-50">
                  <h4 className="text-xs font-black uppercase tracking-wider text-indigo-700 pb-1 border-b border-slate-200 flex items-center gap-1.5">
                    <Sliders className="w-4 h-4" />
                    4. Status, Source, Score & Organization
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">Lead Status</Label>
                      <select
                        value={status}
                        onChange={(e) => setStatus(e.target.value)}
                        className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="New">New</option>
                        <option value="Contacted">Contacted</option>
                        <option value="Qualified">Qualified</option>
                        <option value="Unqualified">Unqualified</option>
                        <option value="Converted">Converted</option>
                      </select>
                    </div>

                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">Lead Source</Label>
                      <select
                        value={source}
                        onChange={(e) => setSource(e.target.value)}
                        className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="Website">Website</option>
                        <option value="LinkedIn">LinkedIn</option>
                        <option value="Referral">Referral</option>
                        <option value="Cold Call">Cold Call</option>
                        <option value="Event">Event</option>
                        <option value="Partner">Partner</option>
                      </select>
                    </div>

                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">Organization *</Label>
                      <select
                        value={organizationId}
                        onChange={(e) => setOrganizationId(e.target.value)}
                        className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      >
                        {isOrgsLoading ? (
                          <option value="">Loading...</option>
                        ) : (
                          organizations.map((org) => (
                            <option key={org.id} value={org.id}>
                              {org.name}
                            </option>
                          ))
                        )}
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-1 items-end">
                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">AI Score (0-100)</Label>
                      <Input
                        type="number"
                        min={0}
                        max={100}
                        placeholder="75"
                        value={score}
                        onChange={(e) => setScore(Number(e.target.value))}
                        className="bg-slate-50 border-slate-300 text-black font-bold text-xs"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <Label className="text-xs font-black text-black">Assigned To User</Label>
                      <select
                        value={assignedTo}
                        onChange={(e) => setAssignedTo(e.target.value)}
                        className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-slate-50 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="">Unassigned (None)</option>
                        {isUsersLoading ? (
                          <option value="" disabled>Loading users...</option>
                        ) : (
                          users.map((u) => (
                            <option key={u.id} value={u.id}>
                              {u.name} ({u.role})
                            </option>
                          ))
                        )}
                      </select>
                    </div>

                    <div className="flex items-center gap-2 pb-2">
                      <input
                        type="checkbox"
                        id="isArchivedCheck"
                        checked={isArchived}
                        onChange={(e) => setIsArchived(e.target.checked)}
                        className="w-4 h-4 text-indigo-600 rounded border-slate-300 focus:ring-indigo-500 cursor-pointer"
                      />
                      <label htmlFor="isArchivedCheck" className="text-xs font-black text-slate-800 cursor-pointer select-none">
                        Archive this lead
                      </label>
                    </div>
                  </div>
                </div>
              )}

              {/* Modal Actions */}
              <div className="pt-4 border-t border-slate-200 flex items-center justify-between gap-3 shrink-0">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleCloseModal}
                  disabled={createLeadMutation.isPending || updateLeadMutation.isPending}
                  className="border-slate-300 text-black font-bold hover:bg-slate-100 text-xs"
                >
                  Cancel
                </Button>

                <div className="flex items-center gap-2">
                  {activeModalTab !== 'contact' && (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        if (activeModalTab === 'company') setActiveModalTab('contact');
                        else if (activeModalTab === 'location') setActiveModalTab('company');
                        else if (activeModalTab === 'organization') setActiveModalTab('location');
                      }}
                      className="border-slate-300 text-slate-800 font-bold hover:bg-slate-100 text-xs"
                    >
                      <ChevronLeft className="w-3.5 h-3.5 mr-1" />
                      Previous
                    </Button>
                  )}

                  {activeModalTab !== 'organization' && (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        if (activeModalTab === 'contact') setActiveModalTab('company');
                        else if (activeModalTab === 'company') setActiveModalTab('location');
                        else if (activeModalTab === 'location') setActiveModalTab('organization');
                      }}
                      className="border-indigo-300 text-indigo-700 bg-indigo-50 hover:bg-indigo-100 font-bold text-xs"
                    >
                      Next Category
                      <ChevronRight className="w-3.5 h-3.5 ml-1" />
                    </Button>
                  )}

                  <Button
                    type="submit"
                    disabled={createLeadMutation.isPending || updateLeadMutation.isPending}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold shadow-sm text-xs px-5"
                  >
                    {createLeadMutation.isPending || updateLeadMutation.isPending ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                        {editingLead ? 'Updating Lead...' : 'Creating Lead...'}
                      </>
                    ) : (
                      editingLead ? 'Save Changes' : 'Create Lead'
                    )}
                  </Button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DELETE CONFIRMATION MODAL DIALOG */}
      {leadToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-md bg-white rounded-2xl border border-slate-300 shadow-2xl overflow-hidden text-black">
            {/* Modal Header */}
            <div className="p-5 border-b border-slate-200 bg-rose-50 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-rose-600 flex items-center justify-center text-white shrink-0">
                  <Trash2 className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-base font-black text-rose-950">Delete Sales Lead</h3>
                  <p className="text-xs font-bold text-rose-700">Confirm permanent lead removal</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setLeadToDelete(null)}
                disabled={deleteLeadMutation.isPending}
                className="p-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-200 transition cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 space-y-4">
              <p className="text-xs font-bold text-slate-700 leading-relaxed">
                Are you sure you want to delete sales lead <span className="font-black text-slate-950">"{leadToDelete.contact_name}"</span> ({leadToDelete.company})?
              </p>
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-900 text-[11px] font-bold">
                âš ï¸ Warning: This action cannot be undone and will permanently remove this lead from the database.
              </div>

              {/* Modal Actions */}
              <div className="pt-2 flex items-center justify-end gap-3">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setLeadToDelete(null)}
                  disabled={deleteLeadMutation.isPending}
                  className="border-slate-300 text-black font-bold hover:bg-slate-100 text-xs"
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  onClick={handleConfirmDelete}
                  disabled={deleteLeadMutation.isPending}
                  className="bg-rose-600 hover:bg-rose-700 text-white font-bold shadow-sm text-xs px-5"
                >
                  {deleteLeadMutation.isPending ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                      Deleting Lead...
                    </>
                  ) : (
                    'Delete Lead'
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ASSIGN LEAD MODAL DIALOG */}
      {assigningLead && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-md bg-white rounded-2xl border border-slate-300 shadow-2xl overflow-hidden text-black">
            {/* Modal Header */}
            <div className="p-5 border-b border-slate-200 bg-indigo-50 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shrink-0">
                  <UserCheck className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-base font-black text-indigo-950">Assign Sales Lead</h3>
                  <p className="text-xs font-bold text-indigo-700">Assign to team member / sales rep</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setAssigningLead(null)}
                disabled={assignLeadMutation.isPending}
                className="p-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-200 transition cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 space-y-4">
              <p className="text-xs font-bold text-slate-700 leading-relaxed">
                Assign sales lead <span className="font-black text-slate-950">"{assigningLead.contact_name}"</span> ({assigningLead.company}) to a team member:
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
                        ðŸš«
                      </div>
                      <span>Unassigned (No Owner)</span>
                    </div>
                    {selectedUserId === '' && <CheckCircle2 className="w-4 h-4 text-white" />}
                  </button>

                  {users.length === 0 ? (
                    <div className="p-3 text-center text-xs font-bold text-slate-500">
                      No team members match "{userSearchTerm}"
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
                  <select
                    value={selectedUserId}
                    onChange={(e) => setSelectedUserId(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-slate-300 bg-white text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-indigo-500 cursor-pointer"
                  >
                    <option value="">Unassigned (No Owner)</option>
                    {users.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.name} ({u.role || 'Sales Rep'}) - {u.email}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Modal Actions */}
              <div className="pt-2 flex items-center justify-end gap-3 border-t border-slate-200">
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
          </div>
        </div>
      )}
    </div>
  );
}
