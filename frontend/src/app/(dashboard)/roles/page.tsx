'use client';

import React, { useState } from 'react';
import {
  ShieldCheck,
  Lock,
  Plus,
  Copy,
  Trash2,
  Edit,
  Download,
  Upload,
  UserCheck,
  History,
  CheckCircle2,
  AlertCircle,
  X,
  Loader2,
  KeyRound,
  Users,
  Shield,
  Layers,
  Star
} from 'lucide-react';
import { ConfirmModal } from '@/components/shared/confirm-modal';
import {
  useRolesQuery,
  useSystemRolesQuery,
  useDefaultRoleQuery,
  usePermissionMatrixQuery,
  useRoleAuditLogsQuery,
  useCreateRoleMutation,
  useUpdateRoleMutation,
  useDeleteRoleMutation,
  useCloneRoleMutation,
  useAssignRoleToUserMutation,
  useSetDefaultRoleMutation,
  useBulkDeleteRolesMutation,
  useImportRolesMutation,
  exportRolesApi,
  RoleItem,
  PermissionItem
} from '@/lib/api/roles';

export default function RolesPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Modal states
  const [isRoleModalOpen, setIsRoleModalOpen] = useState(false);
  const [isCloneModalOpen, setIsCloneModalOpen] = useState(false);
  const [isAssignModalOpen, setIsAssignModalOpen] = useState(false);
  const [isAuditModalOpen, setIsAuditModalOpen] = useState(false);
  const [editingRole, setEditingRole] = useState<RoleItem | null>(null);
  const [cloningRole, setCloningRole] = useState<RoleItem | null>(null);
  const [roleToDelete, setRoleToDelete] = useState<RoleItem | null>(null);

  // Form states
  const [roleName, setRoleName] = useState('');
  const [roleDescription, setRoleDescription] = useState('');
  const [cloneNewName, setCloneNewName] = useState('');
  const [assignUserId, setAssignUserId] = useState('usr-101');
  const [assignRoleId, setAssignRoleId] = useState('');

  // Permission Matrix selection state
  const [selectedPerms, setSelectedPerms] = useState<Set<string>>(new Set());

  // Toast / Alert notifications
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Queries
  const { data: roles = [], isLoading: isRolesLoading } = useRolesQuery();
  const { data: systemRoles = [] } = useSystemRolesQuery();
  const { data: defaultRole } = useDefaultRoleQuery();
  const { data: permissionMatrix = [] } = usePermissionMatrixQuery();
  const { data: auditLogs = [] } = useRoleAuditLogsQuery();

  // Mutations
  const createRoleMutation = useCreateRoleMutation();
  const updateRoleMutation = useUpdateRoleMutation();
  const deleteRoleMutation = useDeleteRoleMutation();
  const cloneRoleMutation = useCloneRoleMutation();
  const assignUserMutation = useAssignRoleToUserMutation();
  const setDefaultMutation = useSetDefaultRoleMutation();
  const bulkDeleteMutation = useBulkDeleteRolesMutation();
  const importRolesMutation = useImportRolesMutation();

  const resetRoleForm = () => {
    setRoleName('');
    setRoleDescription('');
    setSelectedPerms(new Set());
    setEditingRole(null);
  };

  const handleOpenCreateModal = () => {
    resetRoleForm();
    setIsRoleModalOpen(true);
  };

  const handleOpenEditModal = (r: RoleItem) => {
    setEditingRole(r);
    setRoleName(r.name);
    setRoleDescription(r.description || '');
    setSelectedPerms(new Set(r.permissions || []));
    setIsRoleModalOpen(true);
  };

  const handleSaveRoleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!roleName.trim()) return;
    const payload = {
      name: roleName.trim(),
      description: roleDescription.trim(),
      permissions: Array.from(selectedPerms),
    };

    try {
      if (editingRole) {
        await updateRoleMutation.mutateAsync({ id: editingRole.id, payload });
        setSuccessMessage(`Role "${editingRole.name}" updated successfully.`);
      } else {
        await createRoleMutation.mutateAsync(payload);
        setSuccessMessage(`New role "${roleName.trim()}" created successfully.`);
      }
      setIsRoleModalOpen(false);
      resetRoleForm();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to save role.');
    }
  };

  const handleCloneRoleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cloningRole || !cloneNewName.trim()) return;
    try {
      const res = await cloneRoleMutation.mutateAsync({ id: cloningRole.id, new_name: cloneNewName.trim() });
      setSuccessMessage(`Role cloned as "${res.name}".`);
      setIsCloneModalOpen(false);
      setCloningRole(null);
      setCloneNewName('');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to clone role.');
    }
  };

  const handleAssignUserSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignUserId.trim() || !assignRoleId) return;
    try {
      const res = await assignUserMutation.mutateAsync({ userId: assignUserId.trim(), roleId: assignRoleId });
      setSuccessMessage(res.message || 'Role assigned to user.');
      setIsAssignModalOpen(false);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to assign role to user.');
    }
  };

  const handleSetDefault = async (r: RoleItem) => {
    try {
      await setDefaultMutation.mutateAsync(r.id);
      setSuccessMessage(`Role "${r.name}" set as default for new registrations.`);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to set default role.');
    }
  };

  const handleExportSchema = async () => {
    try {
      const res = await exportRolesApi();
      setSuccessMessage('Role permissions schema exported. Download started.');
      window.open(res.download_url, '_blank');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to export role schema.');
    }
  };

  const handleImportSchema = async () => {
    try {
      const res = await importRolesMutation.mutateAsync();
      setSuccessMessage(res.message || 'Role definitions imported successfully.');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to import role schema.');
    }
  };

  const handleDeleteRole = async () => {
    if (!roleToDelete) return;
    try {
      await deleteRoleMutation.mutateAsync(roleToDelete.id);
      setSuccessMessage('Role deleted successfully.');
      setRoleToDelete(null);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete role.');
    }
  };

  const togglePermissionSelection = (permId: string) => {
    const next = new Set(selectedPerms);
    if (next.has(permId)) {
      next.delete(permId);
    } else {
      next.add(permId);
    }
    setSelectedPerms(next);
  };

  const filteredRoles = roles.filter(
    (r) =>
      r.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.description && r.description.toLowerCase().includes(searchTerm.toLowerCase()))
  );

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
            <ShieldCheck className="w-7 h-7 text-indigo-600" />
            Roles & Permissions (RBAC)
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">Configure granular permission matrices for Admins, Managers, Reps & custom organization roles</p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={handleExportSchema}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer"
          >
            <Download className="w-4 h-4 text-slate-600" />
            Export Schema
          </button>

          <button
            onClick={handleImportSchema}
            disabled={importRolesMutation.isPending}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer disabled:opacity-50"
          >
            {importRolesMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4 text-indigo-600" />}
            Import JSON
          </button>

          <button
            onClick={() => setIsAuditModalOpen(true)}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer"
          >
            <History className="w-4 h-4 text-purple-600" />
            Audit Logs
          </button>

          <button
            onClick={handleOpenCreateModal}
            className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-semibold text-sm transition-colors shadow-sm cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            Create Custom Role
          </button>
        </div>
      </div>

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">TOTAL ROLES</p>
            <h3 className="text-2xl font-bold text-slate-900 mt-1">{roles.length} Configured</h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600">
            <ShieldCheck className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">SYSTEM ROLES</p>
            <h3 className="text-2xl font-bold text-purple-600 mt-1">{systemRoles.length} Built-in</h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-purple-50 flex items-center justify-center text-purple-600">
            <Lock className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">PERMISSION MATRIX</p>
            <h3 className="text-2xl font-bold text-emerald-600 mt-1">{permissionMatrix.length} Actions</h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-600">
            <KeyRound className="w-5 h-5" />
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">REGISTRATION DEFAULT</p>
            <h3 className="text-xs font-bold text-slate-900 mt-1 flex items-center gap-1.5">
              <Star className="w-4 h-4 text-amber-500" />
              {defaultRole?.name || 'Sales Rep'}
            </h3>
          </div>
          <div className="h-10 w-10 rounded-lg bg-amber-50 flex items-center justify-center text-amber-600">
            <UserCheck className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Main Roles Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {isRolesLoading ? (
          <div className="col-span-full py-12 flex justify-center items-center gap-2 text-slate-500">
            <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
            <span className="text-xs font-medium">Loading organization roles...</span>
          </div>
        ) : filteredRoles.length === 0 ? (
          <div className="col-span-full py-12 text-center text-slate-400 text-xs italic">
            No organization roles found matching your filter.
          </div>
        ) : (
          filteredRoles.map((role) => {
            const isDefault = defaultRole?.id === role.id;
            return (
              <div
                key={role.id}
                className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4 flex flex-col justify-between"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Shield className="w-5 h-5 text-indigo-600" />
                      <h3 className="text-base font-bold text-slate-900">{role.name}</h3>
                    </div>

                    <div className="flex items-center gap-1">
                      {role.is_system_role && (
                        <span className="px-2 py-0.5 bg-purple-100 text-purple-800 rounded text-[10px] font-bold uppercase">
                          System
                        </span>
                      )}
                      {isDefault && (
                        <span className="px-2 py-0.5 bg-amber-100 text-amber-800 rounded text-[10px] font-bold uppercase flex items-center gap-1">
                          <Star className="w-3 h-3 text-amber-600" />
                          Default
                        </span>
                      )}
                    </div>
                  </div>

                  <p className="text-xs text-slate-500 leading-relaxed">
                    {role.description || 'Custom role configured with assigned action permissions.'}
                  </p>
                </div>

                <div className="pt-4 border-t border-slate-100 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1">
                    {!isDefault && (
                      <button
                        onClick={() => handleSetDefault(role)}
                        title="Set as registration default"
                        className="p-1.5 text-amber-600 hover:bg-amber-50 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                      >
                        <Star className="w-4 h-4" />
                      </button>
                    )}

                    <button
                      onClick={() => {
                        setCloningRole(role);
                        setCloneNewName(`${role.name} Copy`);
                        setIsCloneModalOpen(true);
                      }}
                      title="Clone role"
                      className="p-1.5 text-indigo-600 hover:bg-indigo-50 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                    >
                      <Copy className="w-4 h-4" />
                    </button>

                    <button
                      onClick={() => {
                        setAssignRoleId(role.id);
                        setIsAssignModalOpen(true);
                      }}
                      title="Assign role to user"
                      className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                    >
                      <UserCheck className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleOpenEditModal(role)}
                      title="Edit role permissions"
                      className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
                    >
                      <Edit className="w-4 h-4" />
                    </button>

                    {!role.is_system_role && (
                      <button
                        onClick={() => setRoleToDelete(role)}
                        title="Delete role"
                        className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Create / Edit Role Modal */}
      {isRoleModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-5">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-indigo-600" />
                {editingRole ? 'Edit Role & Permissions' : 'Create Custom Role'}
              </h2>
              <button onClick={() => setIsRoleModalOpen(false)} className="text-slate-400 hover:text-slate-600 p-1 rounded-lg">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveRoleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                  Role Name *
                </label>
                <input
                  type="text"
                  required
                  value={roleName}
                  onChange={(e) => setRoleName(e.target.value)}
                  placeholder="e.g. Regional Sales Director"
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                  Description
                </label>
                <textarea
                  rows={2}
                  value={roleDescription}
                  onChange={(e) => setRoleDescription(e.target.value)}
                  placeholder="e.g. Full pipeline visibility with discount approval permission"
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-2">
                  System Permissions Matrix
                </label>
                <div className="max-h-48 overflow-y-auto space-y-2 pr-1 border border-slate-200 rounded-xl p-3 bg-slate-50/50">
                  {permissionMatrix.map((p) => (
                    <label key={p.id} className="flex items-center justify-between p-2 bg-white rounded-lg border border-slate-200 cursor-pointer">
                      <div>
                        <span className="text-xs font-bold text-slate-900 block">{p.module}: {p.action}</span>
                        <span className="text-[11px] text-slate-500 block">{p.description}</span>
                      </div>
                      <input
                        type="checkbox"
                        checked={selectedPerms.has(p.id)}
                        onChange={() => togglePermissionSelection(p.id)}
                        className="h-4 w-4 text-indigo-600 rounded border-slate-300 focus:ring-indigo-500"
                      />
                    </label>
                  ))}
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
                <button type="button" onClick={() => setIsRoleModalOpen(false)} className="px-4 py-2 text-sm font-medium text-slate-600">
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createRoleMutation.isPending || updateRoleMutation.isPending}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-lg font-medium text-sm cursor-pointer shadow-sm disabled:opacity-50"
                >
                  {(createRoleMutation.isPending || updateRoleMutation.isPending) && (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  )}
                  {editingRole ? 'Save Changes' : 'Create Role'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Clone Role Modal */}
      {isCloneModalOpen && cloningRole && (
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
                  disabled={cloneRoleMutation.isPending}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
                >
                  {cloneRoleMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Clone Role
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Assign Role to User Modal */}
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

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Target Role</label>
                <select
                  value={assignRoleId}
                  onChange={(e) => setAssignRoleId(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {roles.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
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

      {/* Audit History Logs Modal */}
      {isAuditModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <History className="w-5 h-5 text-purple-600" />
                Role Audit Modifications History
              </h3>
              <button onClick={() => setIsAuditModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 max-h-64 overflow-y-auto pr-1">
              {auditLogs.map((log) => (
                <div key={log.id} className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
                  <div className="flex justify-between text-xs font-bold text-slate-900">
                    <span>{log.action}: {log.role_name}</span>
                    <span className="text-slate-400 font-mono text-[10px]">{log.timestamp}</span>
                  </div>
                  <div className="text-[11px] text-slate-500">Performed by: {log.user}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Confirm Delete Modal */}
      {roleToDelete && (
        <ConfirmModal
          isOpen={!!roleToDelete}
          title="Delete Custom Role"
          description={`Are you sure you want to delete role "${roleToDelete.name}"?`}
          confirmText="Delete Role"
          variant="danger"
          onConfirm={handleDeleteRole}
          onClose={() => setRoleToDelete(null)}
        />
      )}
    </div>
  );
}
