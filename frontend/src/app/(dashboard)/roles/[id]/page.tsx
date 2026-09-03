'use client';

import { getErrorMessage } from '@/lib/utils';
import React, { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  ShieldCheck,
  KeyRound,
  Users,
  Star,
  Copy,
  UserCheck,
  Trash2,
  CheckCircle2,
  AlertCircle,
  X,
  Loader2,
  Plus,
  Lock,
  MinusCircle
} from 'lucide-react';
import { ActionMenu } from '@/components/common/action-menu';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { Button } from '@/components/ui/button';
import { ModalShell } from '@/components/common/modal-shell';
import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { PermissionGate } from '@/components/common/permission-gate';
import {
  useRoleQuery,
  useDefaultRoleQuery,
  usePermissionMatrixQuery,
  useRoleUsersQuery,
  useCloneRoleMutation,
  useAssignPermissionsMutation,
  useRemovePermissionMutation,
  useAssignRoleToUserMutation,
  useSetDefaultRoleMutation,
  useDeleteRoleMutation,
  checkPermissionApi,
  PermissionItem
} from '@/lib/api/roles';
import { UserSelect } from '@/components/common/user-select';

export default function RoleDetailPage() {
  const params = useParams();
  const router = useRouter();
  const roleId = (params?.id as string) || '';

  // Queries
  const { data: role, isLoading, isError } = useRoleQuery(roleId);
  const { data: defaultRole } = useDefaultRoleQuery();
  const { data: permissionMatrix = [] } = usePermissionMatrixQuery();
  const { data: assignedUsers = [] } = useRoleUsersQuery(roleId);

  // System roles (e.g. super_admin) are immutable — enforced server-side; UI reflects this.
  const isSystemRole = role?.is_system_role === true;

  // Mutations
  const cloneMutation = useCloneRoleMutation();
  const assignPermsMutation = useAssignPermissionsMutation();
  const removePermMutation = useRemovePermissionMutation();
  const assignUserMutation = useAssignRoleToUserMutation();
  const setDefaultMutation = useSetDefaultRoleMutation();
  const deleteMutation = useDeleteRoleMutation();

  // State
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isCloneModalOpen, setIsCloneModalOpen] = useState(false);
  const [isAssignModalOpen, setIsAssignModalOpen] = useState(false);
  const [isAddPermModalOpen, setIsAddPermModalOpen] = useState(false);
  const [cloneNewName, setCloneNewName] = useState('');
  const [assignUserId, setAssignUserId] = useState('usr-101');
  const [selectedAddPerms, setSelectedAddPerms] = useState<Set<string>>(new Set());

  // Permission Simulator
  const [testPerm, setTestPerm] = useState('leads:create');
  const [testResult, setTestResult] = useState<string | null>(null);

  // Toast / Alert notifications
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Filter permissions assigned to this role (expanding 'all' to all individual granular permissions)
  const assignedPermissions = React.useMemo(() => {
    if (!role || !permissionMatrix.length) return [];
    
    // Exclude generic 'all' placeholder item from permissions table list
    const cleanMatrix = permissionMatrix.filter((p) => p.key !== 'all' && p.id !== 'all' && p.name !== 'All Permission');

    if (role.is_system_role || role.permissions?.includes('all')) {
      return cleanMatrix;
    }
    const permSet = new Set(role.permissions || []);
    return cleanMatrix.filter(
      (p) => permSet.has(p.id) || (p.key && permSet.has(p.key))
    );
  }, [role, permissionMatrix]);

  // DataTable state for assigned permissions
  const [permSearchTerm, setPermSearchTerm] = useState('');
  const [permSelectedIds, setPermSelectedIds] = useState<Set<string>>(new Set());

  const handleBulkRemovePermissions = async () => {
    if (permSelectedIds.size === 0) return;
    try {
      const remaining = (role?.permissions || []).filter((p) => !permSelectedIds.has(p));
      const res = await assignPermsMutation.mutateAsync({
        roleId,
        permissions: remaining,
      });
      setSuccessMessage(res.message || `${permSelectedIds.size} permission(s) removed.`);
      setPermSelectedIds(new Set());
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to remove selected permissions.'));
    }
  };

  const permissionColumns: DataTableColumn<PermissionItem>[] = [
    {
      id: 'name',
      header: 'ACTION PERMISSION',
      cell: (item) => (
        <div className="space-y-0.5">
          <span className="text-xs font-bold text-slate-900 block">{item.name || item.key}</span>
          {item.key && <span className="text-[10px] font-mono text-slate-500 block">{item.key}</span>}
        </div>
      ),
    },
    {
      id: 'category',
      header: 'MODULE / CATEGORY',
      cell: (item) => (
        <span className="px-2.5 py-0.5 bg-indigo-50 text-indigo-700 font-bold rounded-md text-xs border border-indigo-100">
          {item.category || item.module || 'General'}
        </span>
      ),
    },
    {
      id: 'description',
      header: 'DESCRIPTION',
      cell: (item) => (
        <span className="text-xs text-slate-600 font-medium truncate max-w-xs block">
          {item.description || 'System permission action'}
        </span>
      ),
    },
    {
      id: 'actions',
      header: 'ACTIONS',
      cell: (item) =>
        !isSystemRole ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleRemovePermission(item.key || item.id);
            }}
            title="Remove permission from role"
            className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-rose-600 hover:bg-rose-50 rounded-md transition-colors cursor-pointer border border-rose-200"
          >
            <MinusCircle className="w-3.5 h-3.5" />
            Remove
          </button>
        ) : (
          <span className="px-2.5 py-1 text-[11px] font-semibold text-purple-600 bg-purple-50 border border-purple-200 rounded-md">
            Protected
          </span>
        ),
    },
  ];

  const handleOpenAddPermModal = () => {
    setSelectedAddPerms(new Set(role?.permissions || []));
    setIsAddPermModalOpen(true);
  };

  const handleSaveAssignedPermissionsSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await assignPermsMutation.mutateAsync({
        roleId,
        permissions: Array.from(selectedAddPerms),
      });
      setSuccessMessage(res.message || 'Permissions updated successfully.');
      setIsAddPermModalOpen(false);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to update permissions.'));
    }
  };

  const toggleAddPermissionSelection = (perm: PermissionItem) => {
    const next = new Set(selectedAddPerms);
    const key = perm.key || perm.id;
    if (next.has(key) || next.has(perm.id)) {
      next.delete(key);
      next.delete(perm.id);
    } else {
      next.add(key);
    }
    setSelectedAddPerms(next);
  };

  const handleSetDefault = async () => {
    try {
      await setDefaultMutation.mutateAsync(roleId);
      setSuccessMessage(`Role "${role?.name}" set as default for new registrations.`);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to set default role.'));
    }
  };

  const handleCloneRoleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cloneNewName.trim()) return;
    try {
      const res = await cloneMutation.mutateAsync({ id: roleId, new_name: cloneNewName.trim() });
      setSuccessMessage(`Role cloned as "${res.name}".`);
      setIsCloneModalOpen(false);
      setCloneNewName('');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to clone role.'));
    }
  };

  const handleAssignUserSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignUserId.trim()) return;
    try {
      const res = await assignUserMutation.mutateAsync({ userId: assignUserId.trim(), roleId });
      setSuccessMessage(res.message || 'Role assigned to user.');
      setIsAssignModalOpen(false);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to assign role to user.'));
    }
  };

  const handleRemovePermission = async (permIdentifier: string) => {
    try {
      const res = await removePermMutation.mutateAsync({ roleId, permId: permIdentifier });
      setSuccessMessage(res.message || 'Permission removed.');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to remove permission.'));
    }
  };

  const handleCheckPermission = async () => {
    try {
      const res = await checkPermissionApi('usr-1', testPerm);
      setTestResult(res.allowed ? `ALLOWED: User holds permission '${testPerm}'` : `DENIED: Permission missing`);
    } catch (err: unknown) {
      setTestResult(`CHECK FAILED: ${getErrorMessage(err, 'Unknown error')}`);
    }
  };

  const handleDeleteRole = async () => {
    try {
      await deleteMutation.mutateAsync(roleId);
      router.push('/roles');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to delete role.'));
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-2 text-slate-500">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
          <span className="text-sm font-medium">Loading role details...</span>
        </div>
      </div>
    );
  }

  if (isError || !role) {
    return (
      <div className="p-6 max-w-2xl mx-auto space-y-4">
        <Link href="/roles" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900 font-medium">
          <ArrowLeft className="w-4 h-4" />
          Back to Roles & Permissions
        </Link>
        <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 space-y-2">
          <div className="flex items-center gap-2 font-bold text-base">
            <AlertCircle className="w-5 h-5 text-rose-600" />
            Role Not Found
          </div>
          <p className="text-sm">The role configuration you requested could not be found or may have been deleted.</p>
        </div>
      </div>
    );
  }

  const isDefault = defaultRole?.id === role.id;

  return (
    <div className="space-y-6 w-full pb-12">
      {/* Navigation & Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 w-full">
        <div className="space-y-1.5 min-w-0 flex-1">
          <Link href="/roles" className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-indigo-600 transition-colors">
            <ArrowLeft className="w-4 h-4 shrink-0" />
            <span>Back to Roles & Permissions</span>
          </Link>
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2 sm:gap-2.5 break-words">
              <ShieldCheck className="w-5 h-5 sm:w-6 sm:h-6 text-indigo-600 shrink-0" />
              <span>Role: {role.name}</span>
            </h1>
            {role.is_system_role && (
              <span className="px-2.5 py-0.5 bg-purple-100 text-purple-800 border border-purple-200 rounded-full text-xs font-semibold shrink-0">
                Built-in System
              </span>
            )}
            {isDefault && (
              <span className="px-2.5 py-0.5 bg-amber-100 text-amber-800 border border-amber-200 rounded-full text-xs font-semibold flex items-center gap-1 shrink-0">
                <Star className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                <span>Registration Default</span>
              </span>
            )}
          </div>
        </div>

        <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
          <PermissionGate permission="users:roles">
            <Button
              onClick={() => setIsAssignModalOpen(true)}
              className="w-full gap-2 text-xs font-semibold sm:w-auto"
            >
              <UserCheck className="w-4 h-4" />
              <span>Assign to User</span>
            </Button>
          </PermissionGate>

          <ActionMenu
            label="More"
            className="w-full text-xs font-semibold sm:w-auto"
            actions={[
              ...((role.name.toLowerCase().includes('super') || role.name.toLowerCase() === 'super_admin' || role.id === 'sys-admin') && !isDefault ? [{
                label: 'Set registration default',
                permission: 'roles:update' as const,
                icon: setDefaultMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin text-amber-500" /> : <Star className="w-4 h-4 text-amber-500" />,
                disabled: setDefaultMutation.isPending,
                onSelect: handleSetDefault,
              }] : []),
              {
                label: 'Clone role',
                permission: 'roles:create',
                icon: <Copy className="w-4 h-4 text-indigo-600" />,
                onSelect: () => {
                  setCloneNewName(`${role.name} Copy`);
                  setIsCloneModalOpen(true);
                },
              },
              ...(!role.is_system_role && !isDefault && role.type !== 'default' ? [{
                label: 'Delete role',
                permission: 'roles:delete' as const,
                icon: <Trash2 className="w-4 h-4" />,
                variant: 'destructive' as const,
                onSelect: () => setIsDeleteModalOpen(true),
              }] : []),
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
        {/* Left Column: Role Overview & Permissions Matrix */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-6">
            <div className="space-y-1">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider block">Description</span>
              <p className="text-sm text-slate-800 leading-relaxed font-medium">
                {role.description || 'Custom role configured with assigned action permissions.'}
              </p>
            </div>

            <div className="space-y-4 pt-4 border-t border-slate-100">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                  <KeyRound className="w-4 h-4 text-indigo-600" />
                  Assigned Permissions Scope ({assignedPermissions.length} Assigned Actions)
                </h3>
              </div>

              <DataTable<PermissionItem>
                columns={permissionColumns}
                data={assignedPermissions}
                getRowKey={(item) => item.key || item.id}
                emptyTitle="No assigned permissions"
                emptyDescription="No action permissions are currently assigned to this role configuration."
                searchValue={permSearchTerm}
                onSearchChange={setPermSearchTerm}
                searchPlaceholder="Search assigned permissions..."
                maxHeight="500px"
                showCheckbox={!isSystemRole}
                selectedIds={permSelectedIds}
                onToggleRow={(item, checked) => {
                  const key = item.key || item.id;
                  const next = new Set(permSelectedIds);
                  if (checked) next.add(key);
                  else next.delete(key);
                  setPermSelectedIds(next);
                }}
                onToggleAllRows={(checked) => {
                  if (checked) {
                    setPermSelectedIds(new Set(assignedPermissions.map((p) => p.key || p.id)));
                  } else {
                    setPermSelectedIds(new Set());
                  }
                }}
                toolbarActions={
                  isSystemRole ? (
                    <span className="px-3 py-1.5 text-[11px] font-semibold text-purple-700 bg-purple-50 border border-purple-200 rounded-lg">
                      System role is protected — permissions cannot be modified.
                    </span>
                  ) : (
                    <div className="flex items-center gap-2">
                      <PermissionGate permission="roles:assign">
                        {permSelectedIds.size > 0 && (
                          <button
                            onClick={handleBulkRemovePermissions}
                            className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold cursor-pointer transition-colors"
                          >
                            Remove Selected ({permSelectedIds.size})
                          </button>
                        )}
                        <button
                          onClick={handleOpenAddPermModal}
                          className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer shadow-xs"
                        >
                          <Plus className="w-3.5 h-3.5" />
                          Assign Permissions
                        </button>
                      </PermissionGate>
                    </div>
                  )
                }
              />
            </div>
          </div>
        </div>

        {/* Right Column: Assigned Users & Permission Testing */}
        <div className="space-y-6">
          {/* Assigned Users */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3 flex items-center gap-2">
              <Users className="w-4 h-4 text-blue-600" />
              Users Assigned to Role
            </h3>

            <div className="space-y-3">
              {assignedUsers.length === 0 ? (
                <p className="text-xs text-slate-400 italic">No user accounts currently assigned.</p>
              ) : (
                assignedUsers.map((u) => (
                  <div key={u.id} className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-0.5">
                    <span className="text-xs font-bold text-slate-900 block">{u.name}</span>
                    <span className="text-[11px] text-slate-500 font-mono block">{u.email}</span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Live Permission Check Simulator */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3 flex items-center gap-2">
              <Lock className="w-4 h-4 text-purple-600" />
              Permission Checker Simulator
            </h3>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Permission Action Key</label>
                <input
                  type="text"
                  value={testPerm}
                  onChange={(e) => setTestPerm(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 font-mono outline-none"
                />
              </div>

              <button
                onClick={handleCheckPermission}
                className="w-full bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
              >
                Verify Permission
              </button>

              {testResult && (
                <div className="p-3 bg-purple-50 border border-purple-200 text-purple-900 rounded-xl text-xs font-mono">
                  {testResult}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Clone Role Modal */}
      {isCloneModalOpen && (
        <ModalShell
          isOpen={isCloneModalOpen}
          onClose={() => setIsCloneModalOpen(false)}
          title={
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Copy className="w-5 h-5 text-indigo-600" />
              Clone Role Configuration
            </h3>
          }
        >
          <form onSubmit={handleCloneRoleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">New Cloned Role Name *</label>
              <input
                type="text"
                required
                value={cloneNewName}
                onChange={(e) => setCloneNewName(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
              <button type="button" onClick={() => setIsCloneModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                Cancel
              </button>
              <button
                type="submit"
                disabled={cloneMutation.isPending}
                className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
              >
                {cloneMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Clone Role
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* Assign User Modal */}
      {isAssignModalOpen && (
        <ModalShell
          isOpen={isAssignModalOpen}
          onClose={() => setIsAssignModalOpen(false)}
          title={
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <UserCheck className="w-5 h-5 text-blue-600" />
              Assign Role to User Account
            </h3>
          }
        >
          <form onSubmit={handleAssignUserSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Select User Account *</label>
              <UserSelect
                value={assignUserId}
                onChange={setAssignUserId}
              />
            </div>

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
              <button type="button" onClick={() => setIsAssignModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                Cancel
              </button>
              <button
                type="submit"
                disabled={assignUserMutation.isPending}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
              >
                {assignUserMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Assign Role
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* Add Permissions Modal */}
      {isAddPermModalOpen && (
        <ModalShell
          isOpen={isAddPermModalOpen}
          onClose={() => setIsAddPermModalOpen(false)}
          size="lg"
          title={
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <KeyRound className="w-5 h-5 text-indigo-600" />
              Assign Permissions to Role ({selectedAddPerms.size} Selected)
            </h3>
          }
        >
          <form onSubmit={handleSaveAssignedPermissionsSubmit} className="space-y-4">
            <div className="max-h-80 overflow-y-auto space-y-3 pr-1 border border-slate-200 rounded-xl p-3 bg-slate-50/50">
              {Object.entries(
                permissionMatrix.reduce<Record<string, typeof permissionMatrix>>((acc, p) => {
                  const cat = p.category || p.module || 'General';
                  if (!acc[cat]) acc[cat] = [];
                  acc[cat].push(p);
                  return acc;
                }, {})
              ).map(([category, items]) => (
                <div key={category} className="space-y-2 bg-white p-3 rounded-xl border border-slate-200">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                    <span className="px-2.5 py-0.5 bg-indigo-50 text-indigo-700 font-bold rounded-md text-xs border border-indigo-100">
                      {category}
                    </span>
                    <span className="text-[11px] font-semibold text-slate-400">({items.length} permissions)</span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                    {items.map((p) => {
                      const isChecked = selectedAddPerms.has(p.key || p.id) || selectedAddPerms.has(p.id);
                      return (
                        <label
                          key={p.id}
                          className={`flex items-start justify-between p-2 rounded-lg border cursor-pointer transition-colors ${isChecked ? 'bg-indigo-50/50 border-indigo-200' : 'bg-slate-50/50 border-slate-200 hover:bg-slate-100/50'
                            }`}
                        >
                          <div className="space-y-0.5 pr-2">
                            <span className="text-xs font-bold text-slate-900 block leading-tight">
                              {p.name || p.key}
                            </span>
                            {p.key && <span className="text-[10px] font-mono text-slate-500 block">{p.key}</span>}
                          </div>
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggleAddPermissionSelection(p)}
                            className="h-4 w-4 text-indigo-600 rounded border-slate-300 focus:ring-indigo-500 mt-0.5 shrink-0"
                          />
                        </label>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2 border-t border-slate-100">
              <button type="button" onClick={() => setIsAddPermModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                Cancel
              </button>
              <button
                type="submit"
                disabled={assignPermsMutation.isPending}
                className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
              >
                {assignPermsMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Save Permissions
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* Delete Confirm Modal */}
      {isDeleteModalOpen && (
        <ConfirmModal
          isOpen={isDeleteModalOpen}
          title="Delete Custom Role"
          description={`Are you sure you want to delete role "${role.name}"?`}
          confirmText="Delete Role"
          variant="danger"
          onConfirm={handleDeleteRole}
          onClose={() => setIsDeleteModalOpen(false)}
        />
      )}
    </div>
  );
}
