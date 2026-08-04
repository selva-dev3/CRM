'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { 
  Plus, 
  Search, 
  Mail, 
  ShieldCheck, 
  UserCheck, 
  Sliders, 
  ChevronDown, 
  Pencil, 
  Trash2, 
  RefreshCw, 
  Sparkles, 
  X, 
  AlertCircle, 
  CheckCircle2, 
  UserPlus, 
  Power, 
  Ban, 
  User,
  Building
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import { DataTable, type DataTableColumn, type TableActionOption } from '@/components/shared/data-table';
import { 
  useUsersQuery, 
  useUserInvitationsQuery,
  useCreateUserMutation,
  useInviteUsersMutation, 
  useActivateUserMutation, 
  useDeactivateUserMutation, 
  useDeleteUserMutation, 
  UserItem,
  UserInvitationItem,
  deactivateUserApi,
  deleteUserApi
} from '@/lib/api/users';
import { useOrganizationsQuery } from '@/lib/api/organizations';
import { useQueryClient } from '@tanstack/react-query';

export default function UsersPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  // Active Tab State ('all' | 'invites')
  const [activeTab, setActiveTab] = useState<'all' | 'invites'>('all');

  // Search & Pagination State
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [page, setPage] = useState(1);
  const limit = 15;

  // Debounce search input to prevent focus loss & flickering
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
      setPage(1);
    }, 250);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  // Bulk Selection State
  const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(new Set());

  // Queries
  const { data: users = [], isLoading, refetch } = useUsersQuery(page, limit, debouncedSearchTerm);

  // Lazy Invitation Query - ONLY executes when activeTab === 'invites'
  const {
    data: invitations = [],
    isLoading: isInvitationsLoading,
    refetch: refetchInvitations,
  } = useUserInvitationsQuery(undefined, {
    enabled: activeTab === 'invites',
  });

  const { data: organizations = [] } = useOrganizationsQuery();

  // Mutations
  const createUserMutation = useCreateUserMutation();
  const inviteUsersMutation = useInviteUsersMutation();
  const activateUserMutation = useActivateUserMutation();
  const deactivateUserMutation = useDeactivateUserMutation();
  const deleteUserMutation = useDeleteUserMutation();

  // Modal & Notification States
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState<UserItem | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Invite Form State
  const [userName, setUserName] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [userRole, setUserRole] = useState('Representative');
  const [userOrgId, setUserOrgId] = useState('');

  // Create User Direct Form State
  const [createName, setCreateName] = useState('');
  const [createEmail, setCreateEmail] = useState('');
  const [createPassword, setCreatePassword] = useState('');
  const [createRole, setCreateRole] = useState('Representative');
  const [createOrgId, setCreateOrgId] = useState('');

  // Searchable Organization Dropdown States
  const [createOrgSearch, setCreateOrgSearch] = useState('');
  const [isCreateOrgOpen, setIsCreateOrgOpen] = useState(false);
  const [inviteOrgSearch, setInviteOrgSearch] = useState('');
  const [isInviteOrgOpen, setIsInviteOrgOpen] = useState(false);

  // Organization lookup map for DataTable rendering
  const orgMap = useMemo(() => {
    const map = new Map<string, string>();
    organizations.forEach((org) => map.set(org.id, org.name));
    return map;
  }, [organizations]);

  useEffect(() => {
    if (organizations.length > 0) {
      if (!createOrgId) setCreateOrgId(organizations[0].id);
      if (!userOrgId) setUserOrgId(organizations[0].id);
    }
  }, [organizations]);

  const resetForm = () => {
    setUserName('');
    setUserEmail('');
    setUserRole('Representative');
    setUserOrgId(organizations[0]?.id || '');
    setInviteOrgSearch('');
    setIsInviteOrgOpen(false);
    setErrorMessage(null);
  };

  const resetCreateForm = () => {
    setCreateName('');
    setCreateEmail('');
    setCreatePassword('');
    setCreateRole('Representative');
    setCreateOrgId(organizations[0]?.id || '');
    setCreateOrgSearch('');
    setIsCreateOrgOpen(false);
    setErrorMessage(null);
  };

  const handleOpenModal = () => {
    resetForm();
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    resetForm();
  };

  const handleOpenCreateModal = () => {
    resetCreateForm();
    setIsCreateModalOpen(true);
  };

  const handleCloseCreateModal = () => {
    setIsCreateModalOpen(false);
    resetCreateForm();
  };

  const handleAutofillCreate = () => {
    const randomSuffix = Math.floor(100 + Math.random() * 900);
    setCreateName(`User ${randomSuffix}`);
    setCreateEmail(`user${randomSuffix}@crmcompany.com`);
    setCreatePassword('Password123!');
    setCreateRole('Representative');
    setCreateOrgId(organizations[0]?.id || '');
  };

  const handleCreateUserSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createEmail.trim() || !createName.trim()) {
      setErrorMessage('Please fill in both name and email.');
      return;
    }

    try {
      const newUser = await createUserMutation.mutateAsync({
        name: createName.trim(),
        email: createEmail.trim(),
        password: createPassword || 'Password123!',
        role: createRole,
        organization_id: createOrgId || organizations[0]?.id || 'org-1',
      });

      await queryClient.invalidateQueries({ queryKey: ['users'] });
      await refetch();

      setSuccessMessage(`User account "${newUser.name || newUser.email}" created successfully!`);
      setIsCreateModalOpen(false);
      resetCreateForm();

      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to create user account.');
    }
  };

  const handleAutofill = () => {
    const randomSuffix = Math.floor(100 + Math.random() * 900);
    setUserName(`Demo User ${randomSuffix}`);
    setUserEmail(`user${randomSuffix}@example.com`);
    setUserRole('Representative');
    setUserOrgId(organizations[0]?.id || '');
  };

  const handleInviteUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userEmail.trim()) {
      setErrorMessage('Please provide a valid email address.');
      return;
    }

    try {
      await inviteUsersMutation.mutateAsync({
        users: [{ name: userName.trim() || undefined, email: userEmail.trim() }],
        role: userRole,
      });

      await queryClient.invalidateQueries({ queryKey: ['users'] });
      await refetch();

      setSuccessMessage(`Invitation sent successfully to ${userEmail}!`);
      setIsModalOpen(false);
      resetForm();

      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to send invitation.');
    }
  };

  // User Actions (Activate / Deactivate / Delete)
  const handleToggleActivate = async (user: UserItem) => {
    try {
      if (user.is_active) {
        await deactivateUserMutation.mutateAsync(user.id);
        setSuccessMessage(`User "${user.name || user.email}" deactivated.`);
      } else {
        await activateUserMutation.mutateAsync(user.id);
        setSuccessMessage(`User "${user.name || user.email}" activated.`);
      }
      await queryClient.invalidateQueries({ queryKey: ['users'] });
      await refetch();
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to update user status.');
    }
  };

  const handleConfirmDelete = async () => {
    if (!userToDelete) return;
    try {
      await deleteUserMutation.mutateAsync(userToDelete.id);
      await queryClient.invalidateQueries({ queryKey: ['users'] });
      await refetch();
      setSuccessMessage(`User "${userToDelete.name || userToDelete.email}" deleted successfully.`);
      setUserToDelete(null);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to delete user.');
    }
  };

  // Bulk Selection Handlers
  const handleToggleRow = useCallback((user: UserItem, checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(user.id);
      } else {
        next.delete(user.id);
      }
      return next;
    });
  }, []);

  const handleToggleAllRows = useCallback(
    (checked: boolean) => {
      if (checked) {
        setSelectedIds(new Set(users.map((u) => u.id)));
      } else {
        setSelectedIds(new Set());
      }
    },
    [users]
  );

  const handleBulkDeactivate = async () => {
    if (selectedIds.size === 0) return;
    try {
      for (const id of Array.from(selectedIds)) {
        await deactivateUserApi(id).catch(() => null);
      }
      await queryClient.invalidateQueries({ queryKey: ['users'] });
      await refetch();
      setSuccessMessage(`Deactivated ${selectedIds.size} selected user(s).`);
      setSelectedIds(new Set());
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setErrorMessage('Failed to complete bulk deactivate.');
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    try {
      for (const id of Array.from(selectedIds)) {
        await deleteUserApi(id).catch(() => null);
      }
      await queryClient.invalidateQueries({ queryKey: ['users'] });
      await refetch();
      setSuccessMessage(`Deleted ${selectedIds.size} selected user(s).`);
      setSelectedIds(new Set());
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err: any) {
      setErrorMessage('Failed to complete bulk delete.');
    }
  };

  // DataTable Columns Definition
  const columns: DataTableColumn<UserItem>[] = useMemo(
    () => [
      {
        id: 'name',
        header: 'User & Email',
        className: 'min-w-[200px]',
        cell: (item: UserItem) => (
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-[#2563EB]/10 border border-[#2563EB]/20 text-[#2563EB] flex items-center justify-center font-semibold text-caption shrink-0">
              {item.name ? item.name.charAt(0).toUpperCase() : item.email.charAt(0).toUpperCase()}
            </div>
            <div className="space-y-0.5">
              <span className="block text-body font-medium text-[#111827]">{item.name || 'Unnamed User'}</span>
              <div className="flex items-center gap-1.5 text-caption text-[#6B7280]">
                <Mail className="w-3.5 h-3.5 text-[#9CA3AF] shrink-0" />
                <span>{item.email}</span>
              </div>
            </div>
          </div>
        ),
      },
      {
        id: 'role',
        header: 'Role',
        className: 'min-w-[130px]',
        cell: (item: UserItem) => (
          <span
            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-badge font-semibold border ${
              item.role === 'Admin' || item.role === 'Administrator'
                ? 'bg-purple-50 text-purple-700 border-purple-200'
                : item.role === 'Manager'
                ? 'bg-[#16A34A]/10 text-[#16A34A] border-[#16A34A]/20'
                : 'bg-[#2563EB]/10 text-[#2563EB] border-[#2563EB]/20'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5 mr-1 shrink-0" />
            {item.role}
          </span>
        ),
      },
      {
        id: 'organization',
        header: 'Organization',
        className: 'min-w-[160px]',
        cell: (item: UserItem) => {
          const orgName = orgMap.get(item.organization_id) || (item.organization_id ? `Org (${item.organization_id.substring(0, 8)})` : 'Default Organization');
          return (
            <div className="flex items-center gap-1.5 text-body font-medium text-[#374151]">
              <Building className="w-3.5 h-3.5 text-[#2563EB] shrink-0" />
              <span className="truncate">{orgName}</span>
            </div>
          );
        },
      },
      {
        id: 'status',
        header: 'Account Status',
        className: 'min-w-[120px]',
        cell: (item: UserItem) => (
          <span
            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-badge font-semibold border ${
              item.is_active
                ? 'bg-[#16A34A]/10 text-[#16A34A] border-[#16A34A]/20'
                : 'bg-[#F59E0B]/10 text-[#D97706] border-[#F59E0B]/20'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${item.is_active ? 'bg-[#16A34A]' : 'bg-[#D97706]'} mr-1.5`} />
            {item.is_active ? 'Active' : 'Inactive'}
          </span>
        ),
      },
      {
        id: 'created_at',
        header: 'Joined Date',
        className: 'min-w-[120px]',
        cell: (item: UserItem) => (
          <span className="text-body font-medium text-[#6B7280]">
            {item.created_at ? new Date(item.created_at).toLocaleDateString() : 'N/A'}
          </span>
        ),
      },
    ],
    [orgMap]
  );

  // DataTable Columns Definition for Invitations
  const inviteColumns: DataTableColumn<UserInvitationItem>[] = useMemo(
    () => [
      {
        id: 'email',
        header: 'Invited Email & Token',
        className: 'min-w-[220px]',
        cell: (item: UserInvitationItem) => (
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-amber-50 border border-amber-200 text-amber-700 flex items-center justify-center font-semibold text-caption shrink-0">
              {item.email.charAt(0).toUpperCase()}
            </div>
            <div className="space-y-0.5">
              <span className="block text-body font-medium text-[#111827]">{item.email}</span>
              <div className="flex items-center gap-1.5 text-caption text-[#9CA3AF]">
                <Mail className="w-3.5 h-3.5 shrink-0" />
                <span>Token: {item.token}</span>
              </div>
            </div>
          </div>
        ),
      },
      {
        id: 'role',
        header: 'Assigned Role',
        className: 'min-w-[140px]',
        cell: (item: UserInvitationItem) => (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-badge font-semibold border bg-purple-50 text-purple-700 border-purple-200">
            <ShieldCheck className="w-3.5 h-3.5 mr-1 shrink-0" />
            {item.role}
          </span>
        ),
      },
      {
        id: 'organization',
        header: 'Organization',
        className: 'min-w-[160px]',
        cell: (item: UserInvitationItem) => {
          const orgName = orgMap.get(item.organization_id) || (item.organization_id ? `Org (${item.organization_id.substring(0, 8)})` : 'Default Organization');
          return (
            <div className="flex items-center gap-1.5 text-body font-medium text-[#374151]">
              <Building className="w-3.5 h-3.5 text-[#2563EB] shrink-0" />
              <span className="truncate">{orgName}</span>
            </div>
          );
        },
      },
      {
        id: 'status',
        header: 'Invitation Status',
        className: 'min-w-[130px]',
        cell: (item: UserInvitationItem) => (
          <span
            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-badge font-semibold border ${
              item.status === 'accepted'
                ? 'bg-[#16A34A]/10 text-[#16A34A] border-[#16A34A]/20'
                : item.status === 'pending'
                ? 'bg-[#F59E0B]/10 text-[#D97706] border-[#F59E0B]/20'
                : 'bg-gray-100 text-gray-600 border-gray-200'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${item.status === 'accepted' ? 'bg-[#16A34A]' : 'bg-[#D97706]'} mr-1.5`} />
            {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
          </span>
        ),
      },
      {
        id: 'created_at',
        header: 'Invited Date',
        className: 'min-w-[120px]',
        cell: (item: UserInvitationItem) => (
          <span className="text-body font-medium text-[#6B7280]">
            {item.created_at ? new Date(item.created_at).toLocaleDateString() : 'N/A'}
          </span>
        ),
      },
    ],
    [orgMap]
  );

  // Row Actions Definition
  const actions = (user: UserItem): TableActionOption<UserItem>[] => [
    {
      label: user.is_active ? 'Deactivate User' : 'Activate User',
      icon: user.is_active ? <Ban className="w-4 h-4 mr-2 text-[#F59E0B]" /> : <Power className="w-4 h-4 mr-2 text-[#16A34A]" />,
      onClick: (item) => handleToggleActivate(item),
    },
    {
      label: 'Delete User',
      variant: 'destructive',
      icon: <Trash2 className="w-4 h-4 mr-2 text-[#DC2626]" />,
      onClick: (item) => setUserToDelete(item),
    },
  ];

  return (
    <div className="space-y-6 text-[#374151]">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-[#E5E7EB]">
        <div>
          <h1 className="text-page-title">
            User Management
          </h1>
          <p className="text-caption mt-1">
            Manage team members, roles, organization access & invitations
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            onClick={handleOpenCreateModal}
            size="default"
            variant="outline"
            className="shadow-saas-sm px-4 text-button cursor-pointer"
          >
            <Plus className="w-4 h-4 mr-2 text-[#2563EB]" />
            + Create User
          </Button>

          <Button
            type="button"
            onClick={handleOpenModal}
            size="default"
            variant="primary"
            className="shadow-saas-sm px-4 text-button cursor-pointer"
          >
            <UserPlus className="w-4 h-4 mr-2" />
            + Invite User
          </Button>
        </div>
      </div>

      {/* Tabs Navigation Bar */}
      <div className="flex items-center gap-2 border-b border-[#E5E7EB] pb-3">
        <button
          type="button"
          onClick={() => setActiveTab('all')}
          className={`px-4 py-2 text-button font-medium rounded-btn transition-colors cursor-pointer flex items-center gap-2 ${
            activeTab === 'all'
              ? 'bg-[#2563EB]/10 text-[#2563EB] font-semibold border border-[#2563EB]/20 shadow-saas-sm'
              : 'text-[#6B7280] hover:text-[#111827] hover:bg-[#F3F4F6]'
          }`}
        >
          <User className="w-4 h-4" />
          <span>All Users</span>
          <span className="px-2 py-0.5 rounded-full bg-[#E5E7EB] text-[#374151] text-badge font-semibold">
            {users.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('invites')}
          className={`px-4 py-2 text-button font-medium rounded-btn transition-colors cursor-pointer flex items-center gap-2 ${
            activeTab === 'invites'
              ? 'bg-[#2563EB]/10 text-[#2563EB] font-semibold border border-[#2563EB]/20 shadow-saas-sm'
              : 'text-[#6B7280] hover:text-[#111827] hover:bg-[#F3F4F6]'
          }`}
        >
          <Mail className="w-4 h-4" />
          <span>Pending Invites</span>
          {invitations.length > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-[#F59E0B]/20 text-[#D97706] text-badge font-semibold">
              {invitations.length}
            </span>
          )}
        </button>
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

      {/* Conditional Enterprise DataTable (All Users vs Pending Invites) */}
      {activeTab === 'all' ? (
        <DataTable
          columns={columns}
          data={users}
          getRowKey={(item) => item.id}
          onRowClick={(user) => router.push(`/users/${user.id}`)}
          emptyTitle="No team members found"
          emptyDescription="Get started by inviting your team members or clearing your search filter."
          showCheckbox
          selectedIds={selectedIds}
          onToggleRow={handleToggleRow}
          onToggleAllRows={handleToggleAllRows}
          showAvatar
          getAvatarData={(item) => ({ name: item.name || item.email, color: '#2563eb' })}
          actionVariant="menu"
          actions={actions}
          searchValue={searchTerm}
          onSearchChange={setSearchTerm}
          searchPlaceholder="Search team member name or email..."
          isLoading={isLoading}
          pagination={{
            pageIndex: page - 1,
            pageCount: users.length >= limit ? page + 1 : page,
            onPageChange: (p) => setPage(p + 1),
            totalRecords: (page - 1) * limit + users.length,
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
                    {selectedIds.size > 0 ? `Bulk Actions (${selectedIds.size} selected)` : 'Select users below to apply'}
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    disabled={selectedIds.size === 0}
                    onClick={handleBulkDeactivate}
                    className={`cursor-pointer text-button font-medium ${selectedIds.size === 0 ? 'opacity-50 cursor-not-allowed' : 'text-[#374151] hover:bg-[#F3F4F6]'}`}
                  >
                    <Ban className="w-4 h-4 mr-2 text-[#F59E0B]" />
                    <span>Bulk Deactivate ({selectedIds.size})</span>
                  </DropdownMenuItem>
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
      ) : (
        <DataTable
          columns={inviteColumns}
          data={invitations.filter(inv => !searchTerm || inv.email.toLowerCase().includes(searchTerm.toLowerCase()))}
          getRowKey={(item) => item.id}
          emptyTitle="No sent invitations found"
          emptyDescription="Send your first team invitation using the '+ Invite User' button above."
          searchValue={searchTerm}
          onSearchChange={setSearchTerm}
          searchPlaceholder="Search invited email..."
          isLoading={isInvitationsLoading}
          pagination={{ pageSize: 15 }}
          toolbarActions={
            <Button
              type="button"
              variant="outline"
              size="default"
              onClick={() => refetchInvitations()}
              className="text-button font-medium cursor-pointer"
            >
              <RefreshCw className={`w-4 h-4 mr-2 text-[#6B7280] ${isInvitationsLoading ? 'animate-spin' : ''}`} />
              Refresh Invites
            </Button>
          }
        />
      )}

      {/* INVITE USER MODAL DIALOG */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-[#111827]/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-lg bg-white rounded-modal border border-[#E5E7EB] shadow-saas-lg overflow-hidden text-[#111827] flex flex-col">
            {/* Modal Header */}
            <div className="p-5 sm:p-6 border-b border-[#E5E7EB] bg-[#F9FAFB] flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-btn bg-[#2563EB] flex items-center justify-center text-white shadow-saas-sm">
                  <UserPlus className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-subheading font-semibold text-[#111827]">
                    Invite Team Member
                  </h3>
                  <p className="text-caption text-[#6B7280]">
                    Send account invite link and set permissions
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleAutofill}
                  className="text-caption font-medium gap-1.5 cursor-pointer px-3"
                >
                  <Sparkles className="w-3.5 h-3.5 text-[#2563EB] animate-pulse" />
                  <span>Auto-fill Demo</span>
                </Button>
                <button
                  type="button"
                  onClick={handleCloseModal}
                  className="p-1.5 rounded-btn text-[#6B7280] hover:text-[#111827] hover:bg-[#F3F4F6] transition cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <form onSubmit={handleInviteUser} className="p-5 sm:p-6 space-y-4">
              <div>
                <Label htmlFor="name">Full Name</Label>
                <Input
                  id="name"
                  type="text"
                  placeholder="e.g. Alex Rivera"
                  value={userName}
                  onChange={(e) => setUserName(e.target.value)}
                />
              </div>

              <div>
                <Label htmlFor="email">Email Address <span className="text-[#DC2626]">*</span></Label>
                <Input
                  id="email"
                  type="email"
                  required
                  placeholder="e.g. alex@company.com"
                  value={userEmail}
                  onChange={(e) => setUserEmail(e.target.value)}
                />
              </div>

              <div>
                <Label htmlFor="role">User Role</Label>
                <select
                  id="role"
                  value={userRole}
                  onChange={(e) => setUserRole(e.target.value)}
                  className="flex h-10 w-full rounded-input border border-[#E5E7EB] bg-white px-3 py-2 text-input text-[#111827] focus:outline-none focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/20 shadow-saas-sm cursor-pointer"
                >
                  <option value="Representative">Representative / Member</option>
                  <option value="Manager">Manager</option>
                  <option value="Admin">Administrator</option>
                </select>
              </div>

              {/* Organization Selection with Search */}
              <div className="relative">
                <Label htmlFor="invite-org">Organization <span className="text-[#DC2626]">*</span></Label>
                <div
                  onClick={() => setIsInviteOrgOpen(!isInviteOrgOpen)}
                  className="mt-1 flex items-center justify-between h-10 w-full rounded-input border border-[#E5E7EB] bg-white px-3 py-2 text-input text-[#111827] focus:outline-none focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/20 shadow-saas-sm cursor-pointer"
                >
                  <div className="flex items-center gap-2 truncate">
                    <Building className="w-4 h-4 text-[#2563EB] shrink-0" />
                    <span className="font-medium text-[#111827]">
                      {organizations.find((o) => o.id === userOrgId)?.name || 'Select Organization...'}
                    </span>
                  </div>
                  <ChevronDown className="w-4 h-4 text-[#9CA3AF]" />
                </div>

                {isInviteOrgOpen && (
                  <div className="absolute z-50 left-0 right-0 mt-1 bg-white border border-[#E5E7EB] rounded-btn shadow-saas-lg p-2 space-y-2 max-h-56 overflow-y-auto animate-in fade-in-50">
                    <div className="relative">
                      <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-[#9CA3AF]" />
                      <Input
                        type="text"
                        placeholder="Search organization by name..."
                        value={inviteOrgSearch}
                        onChange={(e) => setInviteOrgSearch(e.target.value)}
                        className="pl-8 text-caption h-8"
                        autoFocus
                      />
                    </div>
                    <div className="space-y-0.5 max-h-36 overflow-y-auto">
                      {organizations
                        .filter((org) => org.name.toLowerCase().includes(inviteOrgSearch.toLowerCase()))
                        .map((org) => (
                          <div
                            key={org.id}
                            onClick={() => {
                              setUserOrgId(org.id);
                              setIsInviteOrgOpen(false);
                            }}
                            className={`flex items-center justify-between p-2 rounded-btn text-body font-medium cursor-pointer hover:bg-[#F3F4F6] ${
                              userOrgId === org.id ? 'bg-[#2563EB]/10 text-[#2563EB]' : 'text-[#374151]'
                            }`}
                          >
                            <div className="flex items-center gap-2 truncate">
                              <Building className="w-4 h-4 text-[#6B7280]" />
                              <span>{org.name}</span>
                            </div>
                            {userOrgId === org.id && <CheckCircle2 className="w-4 h-4 text-[#2563EB]" />}
                          </div>
                        ))}
                      {organizations.length === 0 && (
                        <div className="p-3 text-caption text-center text-[#6B7280]">
                          No organizations found
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Modal Footer */}
              <div className="pt-4 border-t border-[#E5E7EB] flex items-center justify-end gap-3">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleCloseModal}
                  className="text-button font-medium cursor-pointer"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  className="shadow-saas-sm text-button font-medium cursor-pointer"
                >
                  Send Invitation
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CREATE USER DIRECT MODAL DIALOG */}
      {isCreateModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-[#111827]/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-lg bg-white rounded-modal border border-[#E5E7EB] shadow-saas-lg overflow-hidden text-[#111827] flex flex-col">
            {/* Modal Header */}
            <div className="p-5 sm:p-6 border-b border-[#E5E7EB] bg-[#F9FAFB] flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-btn bg-[#2563EB] flex items-center justify-center text-white shadow-saas-sm">
                  <Plus className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-subheading font-semibold text-[#111827]">
                    Create New User Account
                  </h3>
                  <p className="text-caption text-[#6B7280]">
                    Directly provision a new team member account
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleAutofillCreate}
                  className="text-caption font-medium gap-1.5 cursor-pointer px-3"
                >
                  <Sparkles className="w-3.5 h-3.5 text-[#2563EB] animate-pulse" />
                  <span>Auto-fill Demo</span>
                </Button>
                <button
                  type="button"
                  onClick={handleCloseCreateModal}
                  className="p-1.5 rounded-btn text-[#6B7280] hover:text-[#111827] hover:bg-[#F3F4F6] transition cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <form onSubmit={handleCreateUserSubmit} className="p-5 sm:p-6 space-y-4">
              <div>
                <Label htmlFor="create-name">Full Name <span className="text-[#DC2626]">*</span></Label>
                <Input
                  id="create-name"
                  type="text"
                  required
                  placeholder="e.g. Alex Rivera"
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                />
              </div>

              <div>
                <Label htmlFor="create-email">Email Address <span className="text-[#DC2626]">*</span></Label>
                <Input
                  id="create-email"
                  type="email"
                  required
                  placeholder="e.g. alex@company.com"
                  value={createEmail}
                  onChange={(e) => setCreateEmail(e.target.value)}
                />
              </div>

              <div>
                <Label htmlFor="create-password">Password</Label>
                <Input
                  id="create-password"
                  type="password"
                  placeholder="Defaults to Password123!"
                  value={createPassword}
                  onChange={(e) => setCreatePassword(e.target.value)}
                />
              </div>

              <div>
                <Label htmlFor="create-role">User Role</Label>
                <select
                  id="create-role"
                  value={createRole}
                  onChange={(e) => setCreateRole(e.target.value)}
                  className="flex h-10 w-full rounded-input border border-[#E5E7EB] bg-white px-3 py-2 text-input text-[#111827] focus:outline-none focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/20 shadow-saas-sm cursor-pointer"
                >
                  <option value="Representative">Representative / Member</option>
                  <option value="Manager">Manager</option>
                  <option value="Admin">Administrator</option>
                </select>
              </div>

              {/* Organization Selection with Search */}
              <div className="relative">
                <Label htmlFor="create-org">Organization <span className="text-[#DC2626]">*</span></Label>
                <div
                  onClick={() => setIsCreateOrgOpen(!isCreateOrgOpen)}
                  className="mt-1 flex items-center justify-between h-10 w-full rounded-input border border-[#E5E7EB] bg-white px-3 py-2 text-input text-[#111827] focus:outline-none focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/20 shadow-saas-sm cursor-pointer"
                >
                  <div className="flex items-center gap-2 truncate">
                    <Building className="w-4 h-4 text-[#2563EB] shrink-0" />
                    <span className="font-medium text-[#111827]">
                      {organizations.find((o) => o.id === createOrgId)?.name || 'Select Organization...'}
                    </span>
                  </div>
                  <ChevronDown className="w-4 h-4 text-[#9CA3AF]" />
                </div>

                {isCreateOrgOpen && (
                  <div className="absolute z-50 left-0 right-0 mt-1 bg-white border border-[#E5E7EB] rounded-btn shadow-saas-lg p-2 space-y-2 max-h-56 overflow-y-auto animate-in fade-in-50">
                    <div className="relative">
                      <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-[#9CA3AF]" />
                      <Input
                        type="text"
                        placeholder="Search organization by name..."
                        value={createOrgSearch}
                        onChange={(e) => setCreateOrgSearch(e.target.value)}
                        className="pl-8 text-caption h-8"
                        autoFocus
                      />
                    </div>
                    <div className="space-y-0.5 max-h-36 overflow-y-auto">
                      {organizations
                        .filter((org) => org.name.toLowerCase().includes(createOrgSearch.toLowerCase()))
                        .map((org) => (
                          <div
                            key={org.id}
                            onClick={() => {
                              setCreateOrgId(org.id);
                              setIsCreateOrgOpen(false);
                            }}
                            className={`flex items-center justify-between p-2 rounded-btn text-body font-medium cursor-pointer hover:bg-[#F3F4F6] ${
                              createOrgId === org.id ? 'bg-[#2563EB]/10 text-[#2563EB]' : 'text-[#374151]'
                            }`}
                          >
                            <div className="flex items-center gap-2 truncate">
                              <Building className="w-4 h-4 text-[#6B7280]" />
                              <span>{org.name}</span>
                            </div>
                            {createOrgId === org.id && <CheckCircle2 className="w-4 h-4 text-[#2563EB]" />}
                          </div>
                        ))}
                      {organizations.length === 0 && (
                        <div className="p-3 text-caption text-center text-[#6B7280]">
                          No organizations found
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Modal Footer */}
              <div className="pt-4 border-t border-[#E5E7EB] flex items-center justify-end gap-3">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleCloseCreateModal}
                  className="text-button font-medium cursor-pointer"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  className="shadow-saas-sm text-button font-medium cursor-pointer"
                >
                  Create User Account
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DELETE USER CONFIRMATION MODAL */}
      {userToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#111827]/60 backdrop-blur-xs animate-in fade-in-50">
          <div className="relative w-full max-w-md bg-white rounded-modal border border-[#E5E7EB] shadow-saas-lg p-6 space-y-4">
            <div className="flex items-center gap-3 text-[#DC2626]">
              <div className="w-10 h-10 rounded-full bg-[#DC2626]/10 flex items-center justify-center shrink-0">
                <Trash2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-subheading font-semibold text-[#111827]">Delete User Account</h3>
                <p className="text-caption text-[#6B7280]">This action cannot be undone.</p>
              </div>
            </div>
            <p className="text-body font-medium text-[#374151]">
              Are you sure you want to delete user account <strong className="text-[#111827]">{userToDelete.name || userToDelete.email}</strong>?
            </p>
            <div className="flex items-center justify-end gap-3 pt-2">
              <Button type="button" variant="outline" onClick={() => setUserToDelete(null)}>
                Cancel
              </Button>
              <Button type="button" variant="danger" onClick={handleConfirmDelete}>
                Delete User
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
