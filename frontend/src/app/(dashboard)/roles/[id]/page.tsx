'use client';

import React, { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  ShieldCheck,
  Shield,
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
import { ConfirmModal } from '@/components/shared/confirm-modal';
import { DataTable, type DataTableColumn } from '@/components/shared/data-table';
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

export default function RoleDetailPage() {
  const params = useParams();
  const router = useRouter();
  const roleId = (params?.id as string) || '';

  // Queries
  const { data: role, isLoading, isError } = useRoleQuery(roleId);
  const { data: defaultRole } = useDefaultRoleQuery();
  const { data: permissionMatrix = [] } = usePermissionMatrixQuery();
  const { data: assignedUsers = [] } = useRoleUsersQuery(roleId);

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

  // Filter permissions assigned to this role
  const assignedPermissions = React.useMemo(() => {
    if (!role || !permissionMatrix.length) return [];
    if (role.is_system_role || role.permissions?.includes('all')) {
      return permissionMatrix;
    }
    const permSet = new Set(role.permissions || []);
    return permissionMatrix.filter(
      (p) => permSet.has(p.id) || (p.key && permSet.has(p.key))
    );
  }, [role, permissionMatrix]);

  const groupedAssignedPermissions = React.useMemo(() => {
    const map: Record<string, PermissionItem[]> = {};
    assignedPermissions.forEach((perm) => {
      const cat = perm.category || perm.module || 'General';
      if (!map[cat]) map[cat] = [];
      map[cat].push(perm);
    });
    return map;
  }, [assignedPermissions]);

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
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to remove selected permissions.');
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
      cell: (item) => (
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
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to update permissions.');
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
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to set default role.');
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
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to clone role.');
    }
  };

  const handleAssignUserSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignUserId.trim()) return;
    try {
      const res = await assignUserMutation.mutateAsync({ userId: assignUserId.trim(), roleId });
      setSuccessMessage(res.message || 'Role assigned to user.');
      setIsAssignModalOpen(false);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to assign role to user.');
    }
  };

  const handleRemovePermission = async (permIdentifier: string) => {
    try {
      const res = await removePermMutation.mutateAsync({ roleId, permId: permIdentifier });
      setSuccessMessage(res.message || 'Permission removed.');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to remove permission.');
    }
  };

  const handleCheckPermission = async () => {
    try {
      const res = await checkPermissionApi('usr-1', testPerm);
      setTestResult(res.allowed ? `ALLOWED: User holds permission '${testPerm}'` : `DENIED: Permission missing`);
    } catch (err: any) {
      setTestResult(`CHECK FAILED: ${err.message}`);
    }
  };

  const handleDeleteRole = async () => {
    try {
      await deleteMutation.mutateAsync(roleId);
      router.push('/roles');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete role.');
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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <Link href="/roles" className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-indigo-600 transition-colors">
            <ArrowLeft className="w-4 h-4" />
            Back to Roles & Permissions
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
              <ShieldCheck className="w-6 h-6 text-indigo-600" />
              Role: {role.name}
            </h1>
            {role.is_system_role && (
              <span className="px-2.5 py-0.5 bg-purple-100 text-purple-800 border border-purple-200 rounded-full text-xs font-semibold">
                Built-in System
              </span>
            )}
            {isDefault && (
              <span className="px-2.5 py-0.5 bg-amber-100 text-amber-800 border border-amber-200 rounded-full text-xs font-semibold flex items-center gap-1">
                <Star className="w-3.5 h-3.5 text-amber-600" />
                Registration Default
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          {!isDefault && (
            <button
              onClick={handleSetDefault}
              className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg text-xs font-semibold shadow-xs cursor-pointer"
            >
              <Star className="w-4 h-4 text-amber-500" />
              Set Registration Default
            </button>
          )}

          <button
            onClick={() => {
              setCloneNewName(`${role.name} Copy`);
              setIsCloneModalOpen(true);
            }}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg text-xs font-semibold shadow-xs cursor-pointer"
          >
            <Copy className="w-4 h-4 text-indigo-600" />
            Clone Role
          </button>

          <button
            onClick={() => setIsAssignModalOpen(true)}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-3.5 py-2 rounded-lg text-xs font-semibold transition-colors cursor-pointer shadow-xs"
          >
            <UserCheck className="w-4 h-4" />
            Assign to User
          </button>

          {!role.is_system_role && (
            <button
              onClick={() => setIsDeleteModalOpen(true)}
              className="flex items-center gap-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 px-3 py-2 rounded-lg text-xs font-semibold shadow-xs cursor-pointer"
            >
              <Trash2 className="w-4 h-4" />
              Delete Role
            </button>
          )}
        </div>
      </div>

      {/* Toast Feedback */}
      {successMessage && (
        <div className="flex items-center justify-between p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl shadow-sm">
          <div className="flex items-center gap-2 text-sm font-medium">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            <span>{successMessage}</span>
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
                showCheckbox={true}
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
                  <div className="flex items-center gap-2">
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
                  </div>
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
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Copy className="w-5 h-5 text-indigo-600" />
                Clone Role Configuration
              </h3>
              <button onClick={() => setIsCloneModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

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

              <div className="flex justify-end gap-3 pt-2">
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
          </div>
        </div>
      )}

      {/* Assign User Modal */}
      {isAssignModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <UserCheck className="w-5 h-5 text-blue-600" />
                Assign Role to User Account
              </h3>
              <button onClick={() => setIsAssignModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAssignUserSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">User Identifier *</label>
                <input
                  type="text"
                  required
                  value={assignUserId}
                  onChange={(e) => setAssignUserId(e.target.value)}
                  placeholder="e.g. usr-101"
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
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
          </div>
        </div>
      )}

      {/* Add Permissions Modal */}
      {isAddPermModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <KeyRound className="w-5 h-5 text-indigo-600" />
                Assign Permissions to Role ({selectedAddPerms.size} Selected)
              </h3>
              <button onClick={() => setIsAddPermModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

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

              <div className="flex justify-end gap-3 pt-2 border-t border-slate-100">
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
          </div>
        </div>
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
