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
  checkPermissionApi
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
  const [cloneNewName, setCloneNewName] = useState('');
  const [assignUserId, setAssignUserId] = useState('usr-101');

  // Permission Simulator
  const [testPerm, setTestPerm] = useState('leads:create');
  const [testResult, setTestResult] = useState<string | null>(null);

  // Toast / Alert notifications
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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

  const handleRemovePermission = async (permId: string) => {
    try {
      const res = await removePermMutation.mutateAsync({ roleId, permId });
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
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                <KeyRound className="w-4 h-4 text-indigo-600" />
                Assigned Permissions Scope
              </h3>

              <div className="space-y-2">
                {permissionMatrix.map((perm) => (
                  <div key={perm.id} className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
                    <div>
                      <span className="text-xs font-bold text-slate-900 block">{perm.module}: {perm.action}</span>
                      <span className="text-[11px] text-slate-500 block">{perm.description}</span>
                    </div>

                    <button
                      onClick={() => handleRemovePermission(perm.id)}
                      title="Remove permission from role"
                      className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg cursor-pointer"
                    >
                      <MinusCircle className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
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
