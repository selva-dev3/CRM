'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import Link from 'next/link';
import {
  Building,
  Plus,
  Search,
  Mail,
  Globe,
  Sliders,
  ChevronDown,
  Pencil,
  Trash2,
  RefreshCw,
  Sparkles,
  X,
  AlertCircle,
  CheckCircle2,
  ShieldCheck,
  Crown,
  Users,
  MapPin,
  Building2,
  Power,
  ArrowLeft,
  UserPlus
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { useHasPermission } from '@/hooks/use-has-permission';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import { DataTable, type DataTableColumn, type TableActionOption } from '@/components/common/data-table';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { PERMISSIONS } from '@/lib/permissions';
import {
  useOrganizationsQuery,
  useCreateOrganizationMutation,
  useUpdateOrganizationMutation,
  useDeleteOrganizationMutation,
  useInviteNewOrganizationMutation,
  OrganizationItem,
  CreateOrganizationPayload,
  UpdateOrganizationPayload,
  deleteOrganizationApi
} from '@/lib/api/organizations';
import { useQueryClient } from '@tanstack/react-query';
import OrganizationDetailPage from './[id]/page';
import { RoleSearchCombobox } from '@/components/features/users/role-search-combobox';

export default function OrganizationPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  // User Role State for RBAC
  const [userRole, setUserRole] = useState<string>('');
  const [userEmail, setUserEmail] = useState<string>('');
  const [isRoleChecked, setIsRoleChecked] = useState(false);
  const { hasPermission } = useHasPermission();

  // Invite Organization permission — the backend independently enforces both keys.
  const canInviteOrganization =
    hasPermission(PERMISSIONS.ORGANIZATION.UPDATE) && hasPermission(PERMISSIONS.INVITATIONS.CREATE);

  useEffect(() => {
    try {
      const userStr = localStorage.getItem('user');
      if (userStr) {
        const u = JSON.parse(userStr);
        const r = u?.role || u?.role_name || '';
        setUserRole(r);
        if (u?.email) setUserEmail(u.email);
      }
    } catch {}
    setIsRoleChecked(true);
  }, []);

  const normalizedRole = userRole.toLowerCase().trim().replace(/[\s_-]+/g, '');
  const cleanEmail = userEmail.toLowerCase().trim();

  // ONLY actual system superadmin (role 'superadmin' OR email 'superadmin@gmail.com') gets multi-tenant list.
  // Standard 'Admin' role or tenant users will ALWAYS get the current organization details view!
  const isSuperAdmin =
    (normalizedRole === 'superadmin' || cleanEmail === 'superadmin@gmail.com') &&
    normalizedRole !== 'admin' &&
    cleanEmail !== 'selvakumar152000@gmail.com';

  // Search & Pagination State
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [page, setPage] = useState(1);
  const limit = 15;

  // Debounce search input
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
      setPage(1);
    }, 250);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  // Bulk Selection State
  const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(new Set());

  // Queries & Mutations
  const { data: rawOrganizations = [], isLoading, refetch } = useOrganizationsQuery();
  const createOrgMutation = useCreateOrganizationMutation();
  const updateOrgMutation = useUpdateOrganizationMutation();
  const deleteOrgMutation = useDeleteOrganizationMutation();
  const inviteNewOrgMutation = useInviteNewOrganizationMutation();

  // Filter organizations by search term
  const organizations = useMemo(() => {
    if (!debouncedSearchTerm.trim()) return rawOrganizations;
    const term = debouncedSearchTerm.toLowerCase();
    return rawOrganizations.filter(
      (org) =>
        org.name?.toLowerCase().includes(term) ||
        org.slug?.toLowerCase().includes(term) ||
        org.email?.toLowerCase().includes(term) ||
        org.domain?.toLowerCase().includes(term) ||
        org.industry?.toLowerCase().includes(term)
    );
  }, [rawOrganizations, debouncedSearchTerm]);

  // Modal & Notification States
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [orgToEdit, setOrgToEdit] = useState<OrganizationItem | null>(null);
  const [orgToDelete, setOrgToDelete] = useState<OrganizationItem | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Invite Organization Modal States — the payload only ever carries
  // { email, full_name, role_id }; no organization_id is collected or sent.
  const [isInviteOrgModalOpen, setIsInviteOrgModalOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteFullName, setInviteFullName] = useState('');
  const [inviteRoleId, setInviteRoleId] = useState('');
  const [inviteErrorMessage, setInviteErrorMessage] = useState<string | null>(null);

  // Form States for Create/Edit
  const [formName, setFormName] = useState('');
  const [formSlug, setFormSlug] = useState('');
  const [formEmail, setFormEmail] = useState('');
  const [formPhone, setFormPhone] = useState('');
  const [formWebsite, setFormWebsite] = useState('');
  const [formDomain, setFormDomain] = useState('');
  const [formIndustry, setFormIndustry] = useState('');
  const [formCountry, setFormCountry] = useState('India');
  const [formCity, setFormCity] = useState('Chennai');
  const [formAddress, setFormAddress] = useState('');
  const [formTaxNumber, setFormTaxNumber] = useState('');
  const [formPlan, setFormPlan] = useState('Free');
  const [formMaxUsers, setFormMaxUsers] = useState(3);
  const [formStatus, setFormStatus] = useState('active');

  const resetForm = () => {
    setFormName('');
    setFormSlug('');
    setFormEmail('');
    setFormPhone('');
    setFormWebsite('');
    setFormDomain('');
    setFormIndustry('Information Technology');
    setFormCountry('India');
    setFormCity('Chennai');
    setFormAddress('');
    setFormTaxNumber('');
    setFormPlan('Free');
    setFormMaxUsers(3);
    setFormStatus('active');
    setErrorMessage(null);
  };

  const handleOpenCreateModal = () => {
    resetForm();
    setIsCreateModalOpen(true);
  };

  const handleOpenEditModal = (org: OrganizationItem) => {
    setOrgToEdit(org);
    setFormName(org.name || '');
    setFormSlug(org.slug || '');
    setFormEmail(org.email || '');
    setFormPhone(org.phone || '');
    setFormWebsite(org.website || '');
    setFormDomain(org.domain || '');
    setFormIndustry(org.industry || 'Information Technology');
    setFormCountry(org.country || 'India');
    setFormCity(org.city || 'Chennai');
    setFormAddress(org.address || '');
    setFormTaxNumber(org.tax_number || '');
    setFormPlan(org.plan || 'Free');
    setFormMaxUsers(org.max_users || 3);
    setFormStatus(org.status || 'active');
    setErrorMessage(null);
  };

  const handleAutofillDemo = () => {
    const randomSuffix = Math.floor(100 + Math.random() * 900);
    const demoName = `Apex Global Corp ${randomSuffix}`;
    const slugified = demoName.toLowerCase().replace(/\s+/g, '-');
    setFormName(demoName);
    setFormSlug(slugified);
    setFormEmail(`contact@apexcorp${randomSuffix}.com`);
    setFormPhone(`+91 987${randomSuffix}5432`);
    setFormWebsite(`https://apexcorp${randomSuffix}.com`);
    setFormDomain(`apexcorp${randomSuffix}.crm.com`);
    setFormIndustry('Software & Cloud Services');
    setFormCountry('India');
    setFormCity('Bengaluru');
    setFormAddress('45 Tech Park Avenue');
    setFormTaxNumber(`GSTIN${randomSuffix}98765`);
    setFormPlan('Free');
    setFormMaxUsers(3);
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim()) {
      setErrorMessage('Please enter an Organization Name.');
      return;
    }

    try {
      const payload: CreateOrganizationPayload = {
        name: formName.trim(),
        slug: formSlug.trim() || formName.trim().toLowerCase().replace(/\s+/g, '-'),
        email: formEmail.trim() || undefined,
        phone: formPhone.trim() || undefined,
        website: formWebsite.trim() || undefined,
        domain: formDomain.trim() || `${formName.trim().toLowerCase().replace(/\s+/g, '-')}.crm.com`,
        industry: formIndustry.trim() || 'Software',
        country: formCountry.trim() || 'India',
        city: formCity.trim() || undefined,
        address: formAddress.trim() || undefined,
        tax_number: formTaxNumber.trim() || undefined,
        plan: 'Free',
        max_users: 3,
        status: formStatus
      };

      const newOrg = await createOrgMutation.mutateAsync(payload);
      await queryClient.invalidateQueries({ queryKey: ['organizations'] });
      await refetch();

      setSuccessMessage(`Organization "${newOrg.name}" created successfully!`);
      setIsCreateModalOpen(false);
      resetForm();
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to create organization.');
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!orgToEdit || !formName.trim()) return;

    try {
      const payload: UpdateOrganizationPayload = {
        name: formName.trim(),
        slug: formSlug.trim() || undefined,
        email: formEmail.trim() || undefined,
        phone: formPhone.trim() || undefined,
        website: formWebsite.trim() || undefined,
        domain: formDomain.trim() || undefined,
        industry: formIndustry.trim() || undefined,
        country: formCountry.trim() || undefined,
        city: formCity.trim() || undefined,
        address: formAddress.trim() || undefined,
        tax_number: formTaxNumber.trim() || undefined,
        plan: formPlan,
        max_users: Number(formMaxUsers) || 100,
        status: formStatus
      };

      await updateOrgMutation.mutateAsync({ id: orgToEdit.id, payload });
      await queryClient.invalidateQueries({ queryKey: ['organizations'] });
      await refetch();

      setSuccessMessage(`Organization "${formName}" updated successfully!`);
      setOrgToEdit(null);
      resetForm();
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to update organization.');
    }
  };

  const handleConfirmDelete = async () => {
    if (!orgToDelete) return;
    try {
      await deleteOrgMutation.mutateAsync(orgToDelete.id);
      await queryClient.invalidateQueries({ queryKey: ['organizations'] });
      await refetch();

      setSuccessMessage(`Organization "${orgToDelete.name}" deleted successfully.`);
      setOrgToDelete(null);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to delete organization.');
    }
  };

  // Bulk Selection Handlers
  const handleToggleRow = useCallback((org: OrganizationItem, checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(org.id);
      } else {
        next.delete(org.id);
      }
      return next;
    });
  }, []);

  const handleToggleAllRows = useCallback(
    (checked: boolean) => {
      if (checked) {
        setSelectedIds(new Set(organizations.map((o) => o.id)));
      } else {
        setSelectedIds(new Set());
      }
    },
    [organizations]
  );

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    try {
      for (const id of Array.from(selectedIds)) {
        await deleteOrganizationApi(id).catch(() => null);
      }
      await queryClient.invalidateQueries({ queryKey: ['organizations'] });
      await refetch();
      setSuccessMessage(`Deleted ${selectedIds.size} selected organization(s).`);
      setSelectedIds(new Set());
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch {
      setErrorMessage('Failed to complete bulk delete.');
    }
  };

  // DataTable Columns Definition
  const columns: DataTableColumn<OrganizationItem>[] = useMemo(
    () => [
      {
        id: 'name',
        header: 'Organization',
        className: 'min-w-[220px]',
        cell: (item: OrganizationItem) => {
          const isValidLogo = Boolean(
            item.logo_url &&
            item.logo_url.trim().length > 0 &&
            item.logo_url !== 'string' &&
            item.logo_url.startsWith('http')
          );
          const initials = item.name
            ? item.name
                .split(' ')
                .map((n) => n[0])
                .join('')
                .substring(0, 2)
                .toUpperCase()
            : 'OR';

          return (
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-[#2563EB]/10 border border-[#2563EB]/20 text-[#2563EB] flex items-center justify-center font-bold text-caption shrink-0 overflow-hidden">
                {isValidLogo ? (
                  <img
                    src={item.logo_url}
                    alt={item.name}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      (e.currentTarget as HTMLImageElement).style.display = 'none';
                    }}
                  />
                ) : (
                  <span>{initials}</span>
                )}
              </div>
              <div className="space-y-0.5 min-w-0">
                <span className="block text-body font-semibold text-[#111827] truncate">{item.name || 'Unnamed Org'}</span>
                <span className="block text-caption font-mono text-[#6B7280] truncate">{item.slug ? `@${item.slug}` : `ID: ${item.id.substring(0, 8)}`}</span>
              </div>
            </div>
          );
        },
      },
      {
        id: 'domain_email',
        header: 'Domain & Contact',
        className: 'min-w-[200px]',
        cell: (item: OrganizationItem) => (
          <div className="space-y-1 text-caption">
            <div className="flex items-center gap-1.5 font-medium text-[#2563EB]">
              <Globe className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">{item.domain || `${item.slug || 'org'}.crm.com`}</span>
            </div>
            {item.email && (
              <div className="flex items-center gap-1.5 text-[#6B7280]">
                <Mail className="w-3.5 h-3.5 shrink-0 text-[#9CA3AF]" />
                <span className="truncate">{item.email}</span>
              </div>
            )}
          </div>
        ),
      },
      {
        id: 'industry',
        header: 'Industry & Region',
        className: 'min-w-[160px]',
        cell: (item: OrganizationItem) => (
          <div className="space-y-0.5">
            <span className="block text-body font-medium text-[#374151] truncate">{item.industry || 'Enterprise Technology'}</span>
            <div className="flex items-center gap-1 text-caption text-[#6B7280]">
              <MapPin className="w-3 h-3 text-[#9CA3AF] shrink-0" />
              <span>{item.country || 'India'}{item.city ? `, ${item.city}` : ''}</span>
            </div>
          </div>
        ),
      },
      {
        id: 'plan',
        header: 'Plan Tier',
        className: 'min-w-[130px]',
        cell: (item: OrganizationItem) => {
          const planName = item.plan || 'Enterprise';
          const isEnterprise = planName.toLowerCase().includes('enterprise');
          const isBusiness = planName.toLowerCase().includes('business') || planName.toLowerCase().includes('pro');

          return (
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-badge font-semibold border ${
                isEnterprise
                  ? 'bg-purple-50 text-purple-700 border-purple-200'
                  : isBusiness
                  ? 'bg-[#2563EB]/10 text-[#2563EB] border-[#2563EB]/20'
                  : 'bg-emerald-50 text-emerald-700 border-emerald-200'
              }`}
            >
              <Crown className="w-3.5 h-3.5 mr-1 shrink-0" />
              {planName}
            </span>
          );
        },
      },
      {
        id: 'max_users',
        header: 'User Seats',
        className: 'min-w-[110px]',
        cell: (item: OrganizationItem) => (
          <div className="flex items-center gap-1.5 text-body font-medium text-[#374151]">
            <Users className="w-3.5 h-3.5 text-[#2563EB] shrink-0" />
            <span>{item.max_users || 100} Seats</span>
          </div>
        ),
      },
      {
        id: 'status',
        header: 'Status',
        className: 'min-w-[110px]',
        cell: (item: OrganizationItem) => {
          const isActive = (item.status || 'active').toLowerCase() === 'active';
          return (
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-badge font-semibold border ${
                isActive
                  ? 'bg-[#16A34A]/10 text-[#16A34A] border-[#16A34A]/20'
                  : 'bg-[#F59E0B]/10 text-[#D97706] border-[#F59E0B]/20'
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${isActive ? 'bg-[#16A34A]' : 'bg-[#D97706]'} mr-1.5`} />
              {isActive ? 'Active' : 'Inactive'}
            </span>
          );
        },
      },
      {
        id: 'created_at',
        header: 'Created Date',
        className: 'min-w-[120px]',
        cell: (item: OrganizationItem) => (
          <span className="text-body font-medium text-[#6B7280]">
            {item.created_at ? new Date(item.created_at).toLocaleDateString() : 'N/A'}
          </span>
        ),
      },
    ],
    []
  );

  // Actions for Row Dropdown
  const actions = (org: OrganizationItem): TableActionOption<OrganizationItem>[] => [
    {
      label: 'Edit Organization',
      permission: PERMISSIONS.ORGANIZATION.UPDATE,
      icon: <Pencil className="w-4 h-4 mr-2 text-[#2563EB]" />,
      onClick: (item) => handleOpenEditModal(item),
    },
    {
      label: 'Delete Organization',
      variant: 'destructive',
      permission: PERMISSIONS.ORGANIZATION.UPDATE,
      icon: <Trash2 className="w-4 h-4 mr-2 text-[#DC2626]" />,
      onClick: (item) => setOrgToDelete(item),
    },
  ];

  const handleOpenInviteMemberModal = () => {
    setInviteEmail('');
    setInviteFullName('');
    setInviteRoleId('');
    setInviteErrorMessage(null);
    setIsInviteOrgModalOpen(true);
  };

  const handleInviteOrgSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const email = inviteEmail.trim();
    const fullName = inviteFullName.trim();
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setInviteErrorMessage('Please enter a valid email address.');
      return;
    }
    if (!fullName) {
      setInviteErrorMessage('Please enter the invitee\'s full name.');
      return;
    }

    try {
      const res = await inviteNewOrgMutation.mutateAsync({
        email,
        full_name: fullName,
      });
      await queryClient.invalidateQueries({ queryKey: ['organizations'] });
      await refetch();
      setSuccessMessage(res.message || `Organization "${res.organization?.name}" created and invitation sent to ${email}.`);
      setIsInviteOrgModalOpen(false);
      setInviteEmail('');
      setInviteFullName('');
      setInviteRoleId('');
      setInviteErrorMessage(null);
      setTimeout(() => setSuccessMessage(null), 6000);
    } catch (err: unknown) {
      setInviteErrorMessage(err instanceof Error ? err.message : 'Failed to create the organization invitation.');
    }
  };

  if (!isSuperAdmin) {
    return <OrganizationDetailPage isCurrentOrgView={true} />;
  }

  return (
    <div className="space-y-6 text-[#374151]">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-[#E5E7EB]">
        <div>
          <h1 className="text-page-title flex items-center gap-2.5">
            <Building2 className="w-6 h-6 text-[#2563EB]" />
            <span>Organization Management</span>
          </h1>
          <p className="text-caption mt-1">
            Manage multi-tenant organizations, domains, seat limits & enterprise subscription tiers
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <Link
            href="/settings"
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 font-semibold text-xs transition shadow-xs cursor-pointer"
          >
            <ArrowLeft className="w-4 h-4 text-slate-500" />
            <span>Back to Settings</span>
          </Link>
          <Button
            type="button"
            onClick={handleOpenInviteMemberModal}
            size="default"
            variant="primary"
            className="shadow-saas-sm px-4 text-button cursor-pointer"
            disabled={!canInviteOrganization}
          >
            <UserPlus className="w-4 h-4 mr-2" />
            Invite Organization
          </Button>
          {isSuperAdmin && (
            <Button
              type="button"
              onClick={handleOpenCreateModal}
              size="default"
              variant="primary"
              className="shadow-saas-sm px-4 text-button cursor-pointer"
            >
              <Plus className="w-4 h-4 mr-2" />
              + Create Organization
            </Button>
          )}
        </div>
      </div>

      {/* Notifications */}
      {successMessage && (
        <div className="p-4 rounded-btn bg-[#16A34A]/10 border border-[#16A34A]/20 text-[#16A34A] text-body font-medium flex items-center gap-2 animate-in fade-in-50">
          <CheckCircle2 className="w-5 h-5 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      {errorMessage && (
        <div className="p-4 rounded-btn bg-[#DC2626]/10 border border-[#DC2626]/20 text-[#DC2626] text-body font-medium flex items-center gap-2 animate-in fade-in-50">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Enterprise Organizations DataTable */}
      <DataTable
        columns={columns}
        data={organizations}
        getRowKey={(item) => item.id}
        onRowClick={(org) => router.push(`/organization/${org.id}`)}
        emptyTitle="No organizations found"
        emptyDescription="Create your first organization or adjust your search filter."
        showCheckbox
        selectedIds={selectedIds}
        onToggleRow={handleToggleRow}
        onToggleAllRows={handleToggleAllRows}
        actionVariant="menu"
        actions={actions}
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search organization name, slug, email or domain..."
        isLoading={isLoading}
        pagination={{
          pageIndex: page - 1,
          pageCount: organizations.length >= limit ? page + 1 : page,
          onPageChange: (p) => setPage(p + 1),
          totalRecords: (page - 1) * limit + organizations.length,
        }}
        toolbarActions={
          <div className="flex items-center gap-2">
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
                  {selectedIds.size > 0 ? `Bulk Actions (${selectedIds.size} selected)` : 'Select orgs below to apply'}
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  disabled={selectedIds.size === 0}
                  onClick={handleBulkDelete}
                  className={`cursor-pointer text-button font-medium ${selectedIds.size === 0 ? 'opacity-50 cursor-not-allowed' : 'text-[#DC2626] hover:bg-[#DC2626]/10'}`}
                >
                  <Trash2 className="w-4 h-4 mr-2 text-[#DC2626]" />
                  <span>Bulk Delete ({selectedIds.size})</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <Button
              type="button"
              variant="outline"
              size="default"
              onClick={() => refetch()}
              className="text-button font-medium cursor-pointer"
            >
              <RefreshCw className={`w-4 h-4 mr-2 text-[#6B7280] ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        }
      />

      {/* INVITE ORGANIZATION MODAL DIALOG */}
      {isInviteOrgModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-[#111827]/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-lg bg-white rounded-modal border border-[#E5E7EB] shadow-saas-lg overflow-hidden text-[#111827] flex flex-col max-h-[90vh]">
            {/* Modal Header */}
            <div className="p-5 sm:p-6 border-b border-[#E5E7EB] bg-[#F9FAFB] flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-btn bg-[#2563EB] flex items-center justify-center text-white shadow-saas-sm">
                  <UserPlus className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-subheading font-semibold text-[#111827]">
                    Invite Organization
                  </h3>
                  <p className="text-caption text-[#6B7280]">
                    Provision a new tenant organization and invite its admin
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsInviteOrgModalOpen(false)}
                className="p-1.5 rounded-btn text-[#6B7280] hover:text-[#111827] hover:bg-[#F3F4F6] transition cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <form onSubmit={handleInviteOrgSubmit} className="p-5 sm:p-6 space-y-4 overflow-y-auto">
              {inviteErrorMessage && (
                <div className="p-4 rounded-btn bg-[#DC2626]/10 border border-[#DC2626]/20 text-[#DC2626] text-body font-medium flex items-center gap-2">
                  <AlertCircle className="w-5 h-5 shrink-0" />
                  <span>{inviteErrorMessage}</span>
                </div>
              )}

              <div>
                <Label htmlFor="invite-email">Email Address <span className="text-[#DC2626]">*</span></Label>
                <Input
                  id="invite-email"
                  type="email"
                  required
                  placeholder="e.g. admin@acme.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                />
                <p className="text-caption text-[#6B7280] mt-1">
                  The invitee becomes the initial admin of a brand-new organization.
                </p>
              </div>

              <div>
                <Label htmlFor="invite-full-name">Full Name <span className="text-[#DC2626]">*</span></Label>
                <Input
                  id="invite-full-name"
                  type="text"
                  required
                  placeholder="e.g. Jane Smith"
                  value={inviteFullName}
                  onChange={(e) => setInviteFullName(e.target.value)}
                />
              </div>

              {/* Modal Actions */}
              <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#E5E7EB]">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsInviteOrgModalOpen(false)}
                  className="cursor-pointer"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={inviteNewOrgMutation.isPending}
                  className="cursor-pointer shadow-saas-sm"
                >
                  {inviteNewOrgMutation.isPending ? 'Sending Invitation...' : 'Send Invitation'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CREATE ORGANIZATION MODAL DIALOG */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-[#111827]/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-2xl bg-white rounded-modal border border-[#E5E7EB] shadow-saas-lg overflow-hidden text-[#111827] flex flex-col max-h-[90vh]">
            {/* Modal Header */}
            <div className="p-5 sm:p-6 border-b border-[#E5E7EB] bg-[#F9FAFB] flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-btn bg-[#2563EB] flex items-center justify-center text-white shadow-saas-sm">
                  <Building className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-subheading font-semibold text-[#111827]">
                    Create New Organization
                  </h3>
                  <p className="text-caption text-[#6B7280]">
                    Add a new enterprise organization tenant
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleAutofillDemo}
                  className="text-caption font-medium gap-1.5 cursor-pointer px-3"
                >
                  <Sparkles className="w-3.5 h-3.5 text-[#2563EB] animate-pulse" />
                  <span>Auto-fill Demo</span>
                </Button>
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="p-1.5 rounded-btn text-[#6B7280] hover:text-[#111827] hover:bg-[#F3F4F6] transition cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <form onSubmit={handleCreateSubmit} className="p-5 sm:p-6 space-y-4 overflow-y-auto">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="create-name">Organization Name <span className="text-[#DC2626]">*</span></Label>
                  <Input
                    id="create-name"
                    required
                    placeholder="e.g. Acme Enterprise Ltd"
                    value={formName}
                    onChange={(e) => {
                      setFormName(e.target.value);
                      if (!formSlug) setFormSlug(e.target.value.toLowerCase().replace(/\s+/g, '-'));
                    }}
                  />
                </div>

                <div>
                  <Label htmlFor="create-slug">Slug Identifier</Label>
                  <Input
                    id="create-slug"
                    placeholder="e.g. acme-enterprise"
                    value={formSlug}
                    onChange={(e) => setFormSlug(e.target.value)}
                    className="font-mono"
                  />
                </div>

                <div>
                  <Label htmlFor="create-email">Official Email</Label>
                  <Input
                    id="create-email"
                    type="email"
                    placeholder="e.g. info@acme.com"
                    value={formEmail}
                    onChange={(e) => setFormEmail(e.target.value)}
                  />
                </div>

                <div>
                  <Label htmlFor="create-phone">Phone Number</Label>
                  <Input
                    id="create-phone"
                    placeholder="e.g. +91 9876543210"
                    value={formPhone}
                    onChange={(e) => setFormPhone(e.target.value)}
                  />
                </div>

                <div>
                  <Label htmlFor="create-domain">Custom Domain</Label>
                  <Input
                    id="create-domain"
                    placeholder="e.g. acme.crm.com"
                    value={formDomain}
                    onChange={(e) => setFormDomain(e.target.value)}
                    className="font-mono text-caption"
                  />
                </div>

                <div>
                  <Label htmlFor="create-industry">Industry Sector</Label>
                  <Input
                    id="create-industry"
                    placeholder="e.g. Information Technology"
                    value={formIndustry}
                    onChange={(e) => setFormIndustry(e.target.value)}
                  />
                </div>

                <div>
                  <Label htmlFor="create-country">Country</Label>
                  <Input
                    id="create-country"
                    placeholder="e.g. India"
                    value={formCountry}
                    onChange={(e) => setFormCountry(e.target.value)}
                  />
                </div>

                <div>
                  <Label htmlFor="create-city">City</Label>
                  <Input
                    id="create-city"
                    placeholder="e.g. Chennai"
                    value={formCity}
                    onChange={(e) => setFormCity(e.target.value)}
                  />
                </div>

                <div>
                  <Label htmlFor="create-plan">Subscription Plan</Label>
                  <select
                    id="create-plan"
                    value="Free"
                    disabled
                    className="w-full h-10 rounded-btn border border-[#E5E7EB] bg-[#F9FAFB] px-3 text-body font-medium text-[#111827] cursor-not-allowed opacity-90"
                  >
                    <option value="Free">Free Plan (Default)</option>
                  </select>
                  <p className="text-caption text-[#6B7280] mt-1">All new organizations start on the Free Plan by default.</p>
                </div>

                <div>
                  <Label htmlFor="create-users">User Seats Limit</Label>
                  <Input
                    id="create-users"
                    type="number"
                    value={3}
                    disabled
                    className="bg-[#F9FAFB] cursor-not-allowed font-mono opacity-90"
                  />
                  <p className="text-caption text-[#6B7280] mt-1">Free Plan includes 3 user seats by default.</p>
                </div>
              </div>

              {/* Modal Actions */}
              <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#E5E7EB]">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="cursor-pointer"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={createOrgMutation.isPending}
                  className="cursor-pointer shadow-saas-sm"
                >
                  {createOrgMutation.isPending ? 'Creating...' : 'Create Organization'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* EDIT ORGANIZATION MODAL DIALOG */}
      {orgToEdit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-[#111827]/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-2xl bg-white rounded-modal border border-[#E5E7EB] shadow-saas-lg overflow-hidden text-[#111827] flex flex-col max-h-[90vh]">
            {/* Modal Header */}
            <div className="p-5 sm:p-6 border-b border-[#E5E7EB] bg-[#F9FAFB] flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-btn bg-[#2563EB] flex items-center justify-center text-white shadow-saas-sm">
                  <Pencil className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-subheading font-semibold text-[#111827]">
                    Edit Organization Details
                  </h3>
                  <p className="text-caption text-[#6B7280]">
                    Update settings for "{orgToEdit.name}"
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setOrgToEdit(null)}
                className="p-1.5 rounded-btn text-[#6B7280] hover:text-[#111827] hover:bg-[#F3F4F6] transition cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <form onSubmit={handleEditSubmit} className="p-5 sm:p-6 space-y-4 overflow-y-auto">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="edit-name">Organization Name <span className="text-[#DC2626]">*</span></Label>
                  <Input
                    id="edit-name"
                    required
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                  />
                </div>

                <div>
                  <Label htmlFor="edit-slug">Slug Identifier</Label>
                  <Input
                    id="edit-slug"
                    value={formSlug}
                    onChange={(e) => setFormSlug(e.target.value)}
                    className="font-mono"
                  />
                </div>

                <div>
                  <Label htmlFor="edit-email">Official Email</Label>
                  <Input
                    id="edit-email"
                    type="email"
                    value={formEmail}
                    onChange={(e) => setFormEmail(e.target.value)}
                  />
                </div>

                <div>
                  <Label htmlFor="edit-phone">Phone Number</Label>
                  <Input
                    id="edit-phone"
                    value={formPhone}
                    onChange={(e) => setFormPhone(e.target.value)}
                  />
                </div>

                <div>
                  <Label htmlFor="edit-domain">Custom Domain</Label>
                  <Input
                    id="edit-domain"
                    value={formDomain}
                    onChange={(e) => setFormDomain(e.target.value)}
                    className="font-mono text-caption"
                  />
                </div>

                <div>
                  <Label htmlFor="edit-industry">Industry Sector</Label>
                  <Input
                    id="edit-industry"
                    value={formIndustry}
                    onChange={(e) => setFormIndustry(e.target.value)}
                  />
                </div>

                <div>
                  <Label htmlFor="edit-country">Country</Label>
                  <Input
                    id="edit-country"
                    value={formCountry}
                    onChange={(e) => setFormCountry(e.target.value)}
                  />
                </div>

                <div>
                  <Label htmlFor="edit-city">City</Label>
                  <Input
                    id="edit-city"
                    value={formCity}
                    onChange={(e) => setFormCity(e.target.value)}
                  />
                </div>

                <div>
                  <Label htmlFor="edit-plan">Subscription Plan</Label>
                  <select
                    id="edit-plan"
                    value={formPlan}
                    onChange={(e) => setFormPlan(e.target.value)}
                    className="w-full h-10 rounded-btn border border-[#E5E7EB] bg-white px-3 text-body font-medium text-[#111827] focus:outline-none focus:ring-2 focus:ring-[#2563EB]"
                  >
                    <option value="Free">Free Plan</option>
                    <option value="Starter">Starter Plan</option>
                    <option value="Professional">Professional Plan</option>
                    <option value="Business">Business Plan</option>
                    <option value="Enterprise">Enterprise Plan</option>
                  </select>
                </div>

                <div>
                  <Label htmlFor="edit-users">User Seats Limit</Label>
                  <Input
                    id="edit-users"
                    type="number"
                    min={1}
                    value={formMaxUsers}
                    onChange={(e) => setFormMaxUsers(Number(e.target.value))}
                  />
                </div>
              </div>

              {/* Modal Actions */}
              <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#E5E7EB]">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setOrgToEdit(null)}
                  className="cursor-pointer"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={updateOrgMutation.isPending}
                  className="cursor-pointer shadow-saas-sm"
                >
                  {updateOrgMutation.isPending ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CONFIRM DELETE MODAL */}
      <ConfirmModal
        isOpen={Boolean(orgToDelete)}
        onClose={() => setOrgToDelete(null)}
        onConfirm={handleConfirmDelete}
        title="Delete Organization"
        description={`Are you sure you want to delete organization "${orgToDelete?.name}"? This action cannot be undone.`}
        confirmText="Delete Organization"
        variant="default"
        isLoading={deleteOrgMutation.isPending}
      />
    </div>
  );
}
