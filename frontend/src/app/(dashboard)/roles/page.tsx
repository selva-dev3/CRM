'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
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
  Shield,
  Star,
  Calendar,
  Layers,
  MoreHorizontal,
  Search,
  ChevronDown,
  Check
} from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/shared/data-table';
import { ConfirmModal } from '@/components/shared/confirm-modal';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator
} from '@/components/ui/dropdown-menu';
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
  useCreatePermissionMutation,
  useBatchImportPermissionsMutation,
  exportRolesApi,
  RoleItem,
  PermissionItem
} from '@/lib/api/roles';
import { useUsersQuery } from '@/lib/api/users';

function UserSelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (val: string) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Live GET /api/v1/users?page=1&limit=100&search=... API call on typing!
  const { data: fetchedUsers = [], isLoading } = useUsersQuery(1, 100, debouncedSearch.trim() || undefined);

  const selectedUser = useMemo(() => {
    return fetchedUsers.find((u) => u.id === value);
  }, [fetchedUsers, value]);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full h-9 rounded-md border border-slate-200 bg-white px-3 text-left text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 flex items-center justify-between cursor-pointer"
      >
        <span className={selectedUser ? 'text-slate-900 font-semibold' : 'text-slate-400'}>
          {selectedUser ? `${selectedUser.name} (${selectedUser.email || selectedUser.id})` : '-- Select User Account --'}
        </span>
        <ChevronDown className="w-3.5 h-3.5 text-slate-400 shrink-0" />
      </button>

      {isOpen && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-slate-200 bg-white shadow-xl p-2 space-y-1.5 animate-in fade-in-50">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search user by name or email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full h-8 pl-8 pr-2 text-xs rounded-md border border-slate-200 bg-slate-50 text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
              autoFocus
            />
          </div>

          <div className="max-h-48 overflow-y-auto space-y-0.5">
            <button
              type="button"
              onClick={() => {
                onChange('');
                setIsOpen(false);
                setSearch('');
              }}
              className="w-full px-2 py-1.5 text-left text-xs text-slate-500 hover:bg-slate-100 rounded cursor-pointer"
            >
              -- None / Clear Selection --
            </button>
            {isLoading ? (
              <div className="px-2 py-3 text-xs text-slate-500 text-center flex items-center justify-center gap-2 font-medium">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-600" />
                <span>Searching users via API...</span>
              </div>
            ) : fetchedUsers.length === 0 ? (
              <div className="px-2 py-2 text-xs text-slate-400 text-center">No matching users found</div>
            ) : (
              fetchedUsers.map((u) => (
                <button
                  key={u.id}
                  type="button"
                  onClick={() => {
                    onChange(u.id);
                    setIsOpen(false);
                    setSearch('');
                  }}
                  className={`w-full px-2 py-1.5 text-left text-xs rounded transition flex items-center justify-between cursor-pointer ${
                    value === u.id ? 'bg-blue-50 text-blue-700 font-bold' : 'text-slate-800 hover:bg-slate-100'
                  }`}
                >
                  <div className="flex flex-col">
                    <span>{u.name}</span>
                    <span className="text-[10px] text-slate-400 font-normal">{u.email || u.id}</span>
                  </div>
                  {value === u.id && <Check className="w-3.5 h-3.5 text-blue-600 shrink-0" />}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function RolesPage() {
  const router = useRouter();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(1);
  const limit = 15;

  // Modal states
  const [isRoleModalOpen, setIsRoleModalOpen] = useState(false);
  const [isCloneModalOpen, setIsCloneModalOpen] = useState(false);
  const [isAssignModalOpen, setIsAssignModalOpen] = useState(false);
  const [isAuditModalOpen, setIsAuditModalOpen] = useState(false);
  const [isPermModalOpen, setIsPermModalOpen] = useState(false);
  const [editingRole, setEditingRole] = useState<RoleItem | null>(null);
  const [cloningRole, setCloningRole] = useState<RoleItem | null>(null);
  const [roleToDelete, setRoleToDelete] = useState<RoleItem | null>(null);

  // Form states
  const [roleName, setRoleName] = useState('');
  const [roleDescription, setRoleDescription] = useState('');
  const [cloneNewName, setCloneNewName] = useState('');
  const [assignUserId, setAssignUserId] = useState('usr-101');
  const [assignRoleId, setAssignRoleId] = useState('');
  const [selectedPerms, setSelectedPerms] = useState<Set<string>>(new Set());

  // Create Permission form states
  const [permMode, setPermMode] = useState<'single' | 'json'>('single');
  const [permName, setPermName] = useState('');
  const [permKey, setPermKey] = useState('');
  const [permCategory, setPermCategory] = useState('Leads');
  const [permDesc, setPermDesc] = useState('');
  const [jsonText, setJsonText] = useState('');
  const [jsonFileName, setJsonFileName] = useState<string | null>(null);

  // Toast / Alert notifications
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Queries
  const { data: roles = [], isLoading: isRolesLoading } = useRolesQuery();
  const { data: systemRoles = [] } = useSystemRolesQuery();
  const { data: defaultRole } = useDefaultRoleQuery();
  const { data: permissionMatrix = [] } = usePermissionMatrixQuery();
  const { data: auditLogs = [] } = useRoleAuditLogsQuery();
  const { data: usersList = [] } = useUsersQuery(1, 100);

  // Mutations
  const createRoleMutation = useCreateRoleMutation();
  const updateRoleMutation = useUpdateRoleMutation();
  const deleteRoleMutation = useDeleteRoleMutation();
  const cloneRoleMutation = useCloneRoleMutation();
  const assignUserMutation = useAssignRoleToUserMutation();
  const setDefaultMutation = useSetDefaultRoleMutation();
  const bulkDeleteMutation = useBulkDeleteRolesMutation();
  const importRolesMutation = useImportRolesMutation();
  const createPermMutation = useCreatePermissionMutation();
  const batchImportPermMutation = useBatchImportPermissionsMutation();

  const handleCreatePermSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!permName.trim() || !permKey.trim()) return;
    try {
      const res = await createPermMutation.mutateAsync({
        name: permName.trim(),
        key: permKey.trim(),
        category: permCategory,
        description: permDesc.trim(),
      });
      setSuccessMessage(`Permission '${res.name || res.key}' created successfully.`);
      setIsPermModalOpen(false);
      setPermName('');
      setPermKey('');
      setPermDesc('');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to create permission.');
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setJsonFileName(file.name);
    const reader = new FileReader();
    reader.onload = (evt) => {
      const content = evt.target?.result as string;
      setJsonText(content);
    };
    reader.readAsText(file);
  };

  const handleBatchImportSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!jsonText.trim()) return;
    try {
      const parsed = JSON.parse(jsonText);
      if (!Array.isArray(parsed)) {
        setErrorMessage('Invalid JSON format: Expected an array of permission objects.');
        return;
      }
      const res = await batchImportPermMutation.mutateAsync(parsed);
      setSuccessMessage(res.message || `Imported ${parsed.length} permissions successfully.`);
      setIsPermModalOpen(false);
      setJsonText('');
      setJsonFileName(null);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to parse JSON file.');
    }
  };

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

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    try {
      const res = await bulkDeleteMutation.mutateAsync(Array.from(selectedIds));
      setSuccessMessage(`${res.affected_count || selectedIds.size} role(s) deleted.`);
      setSelectedIds(new Set());
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete selected roles.');
    }
  };

  const togglePermissionSelection = (perm: PermissionItem) => {
    const next = new Set(selectedPerms);
    const isSelected = next.has(perm.id) || (perm.key ? next.has(perm.key) : false);
    if (isSelected) {
      if (perm.id) next.delete(perm.id);
      if (perm.key) next.delete(perm.key);
    } else {
      if (perm.key) next.add(perm.key);
      else if (perm.id) next.add(perm.id);
    }
    setSelectedPerms(next);
  };

  const groupedPermissions = React.useMemo(() => {
    const map: Record<string, PermissionItem[]> = {};
    permissionMatrix.forEach((p) => {
      const cat = p.category || p.module || 'General';
      if (!map[cat]) map[cat] = [];
      map[cat].push(p);
    });
    return map;
  }, [permissionMatrix]);

  const toggleModulePermissions = (category: string) => {
    const items = groupedPermissions[category] || [];
    const next = new Set(selectedPerms);
    const allSelected = items.every((item) => next.has(item.id) || (item.key && next.has(item.key)));

    items.forEach((item) => {
      if (allSelected) {
        if (item.id) next.delete(item.id);
        if (item.key) next.delete(item.key);
      } else {
        if (item.key) next.add(item.key);
        else if (item.id) next.add(item.id);
      }
    });
    setSelectedPerms(next);
  };

  const toggleAllMatrixPermissions = () => {
    const next = new Set(selectedPerms);
    const allSelected = permissionMatrix.length > 0 && permissionMatrix.every((p) => next.has(p.id) || (p.key && next.has(p.key)));

    permissionMatrix.forEach((p) => {
      if (allSelected) {
        if (p.id) next.delete(p.id);
        if (p.key) next.delete(p.key);
      } else {
        if (p.key) next.add(p.key);
        else if (p.id) next.add(p.id);
      }
    });
    setSelectedPerms(next);
  };

  // DataTable Columns definition
  const columns: DataTableColumn<RoleItem>[] = [
    {
      id: 'name',
      header: 'ROLE NAME',
      cell: (item) => {
        const isDefault = defaultRole?.id === item.id;
        return (
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 font-bold shrink-0">
              <Shield className="w-4 h-4" />
            </div>
            <div>
              <div
                onClick={(e) => {
                  e.stopPropagation();
                  router.push(`/roles/${item.id}`);
                }}
                className="font-bold text-slate-900 hover:text-indigo-600 cursor-pointer transition-colors text-xs flex items-center gap-2"
              >
                {item.name}
                {isDefault && (
                  <span className="px-2 py-0.5 bg-amber-100 text-amber-800 rounded text-[10px] font-bold uppercase flex items-center gap-1">
                    <Star className="w-3 h-3 text-amber-600" />
                    Default
                  </span>
                )}
              </div>
              <div className="text-[11px] text-slate-400 truncate max-w-xs">{item.description || 'Custom organization role'}</div>
            </div>
          </div>
        );
      },
    },
    {
      id: 'is_system_role',
      header: 'TYPE',
      cell: (item) => (
        <span
          className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${item.is_system_role
              ? 'bg-purple-50 text-purple-700 border-purple-200'
              : 'bg-blue-50 text-blue-700 border-blue-200'
            }`}
        >
          {item.type}
        </span>
      ),
    },
    {
      id: 'permissions',
      header: 'PERMISSIONS SCOPE',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-xs text-slate-700 font-medium">
          <KeyRound className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.permissions ? `${item.permissions.length} Action(s)` : 'Full Access'}</span>
        </div>
      ),
    },
    {
      id: 'created_at',
      header: 'CREATED DATE',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-medium">
          <Calendar className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.created_at ? item.created_at.substring(0, 10) : '2026-08-05'}</span>
        </div>
      ),
    },
    {
      id: 'actions',
      header: 'ACTIONS',
      cell: (item) => {
        const isDefault = defaultRole?.id === item.id;
        return (
          <div onClick={(e) => e.stopPropagation()}>
            <DropdownMenu>
              <DropdownMenuTrigger className="p-1.5 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer text-slate-500 hover:text-slate-900 border border-transparent hover:border-slate-200 outline-none">
                <MoreHorizontal className="w-4 h-4" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                {!isDefault && (
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      handleSetDefault(item);
                    }}
                    className="flex items-center gap-2 text-xs font-semibold cursor-pointer text-amber-700 hover:bg-amber-50"
                  >
                    <Star className="w-3.5 h-3.5 text-amber-500" />
                    Set Registration Default
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem
                  onClick={(e) => {
                    e.stopPropagation();
                    setCloningRole(item);
                    setCloneNewName(`${item.name} Copy`);
                    setIsCloneModalOpen(true);
                  }}
                  className="flex items-center gap-2 text-xs font-semibold cursor-pointer text-slate-700 hover:bg-slate-50"
                >
                  <Copy className="w-3.5 h-3.5 text-indigo-600" />
                  Clone Role Configuration
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={(e) => {
                    e.stopPropagation();
                    setAssignRoleId(item.id);
                    setIsAssignModalOpen(true);
                  }}
                  className="flex items-center gap-2 text-xs font-semibold cursor-pointer text-slate-700 hover:bg-slate-50"
                >
                  <UserCheck className="w-3.5 h-3.5 text-blue-600" />
                  Assign Role to User
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={(e) => {
                    e.stopPropagation();
                    handleOpenEditModal(item);
                  }}
                  className="flex items-center gap-2 text-xs font-semibold cursor-pointer text-slate-700 hover:bg-slate-50"
                >
                  <Edit className="w-3.5 h-3.5 text-slate-500" />
                  Edit Role & Permissions
                </DropdownMenuItem>
                {!item.is_system_role && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      onClick={(e) => {
                        e.stopPropagation();
                        setRoleToDelete(item);
                      }}
                      className="flex items-center gap-2 text-xs font-semibold cursor-pointer text-rose-600 hover:bg-rose-50"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-rose-600" />
                      Delete Custom Role
                    </DropdownMenuItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        );
      },
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
            onClick={() => setIsPermModalOpen(true)}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3 py-2 rounded-lg font-semibold text-xs transition-colors shadow-sm cursor-pointer"
          >
            <KeyRound className="w-4 h-4 text-emerald-600" />
            + New Permission
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

      {/* Main DataTable */}
      <DataTable<RoleItem>
        columns={columns}
        data={roles}
        getRowKey={(item) => item.id}
        onRowClick={(item) => router.push(`/roles/${item.id}`)}
        emptyTitle="No roles found"
        emptyDescription="Create a new custom role or clear your search term."
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search role name or description..."
        toolbarActions={
          selectedIds.size > 0 ? (
            <div className="flex items-center gap-2 bg-indigo-50 px-3 py-1 rounded-lg border border-indigo-200">
              <span className="text-xs font-semibold text-indigo-700">{selectedIds.size} selected</span>
              <button
                onClick={handleBulkDelete}
                className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded text-xs font-semibold cursor-pointer"
              >
                Bulk Delete
              </button>
            </div>
          ) : null
        }
        isLoading={isRolesLoading}
        pagination={{
          pageIndex: page - 1,
          pageCount: roles.length >= limit ? page + 1 : page,
          onPageChange: (p) => setPage(p + 1),
          totalRecords: (page - 1) * limit + roles.length,
        }}
      />

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
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-600">
                    System Permissions Matrix ({permissionMatrix.length} Actions)
                  </label>
                  <div className="flex items-center gap-3">
                    <span className="text-[11px] text-indigo-600 font-semibold">{selectedPerms.size} Selected</span>
                    <button
                      type="button"
                      onClick={toggleAllMatrixPermissions}
                      className="text-[11px] font-bold text-indigo-600 hover:text-indigo-800 transition-colors cursor-pointer underline"
                    >
                      {permissionMatrix.length > 0 && permissionMatrix.every((p) => selectedPerms.has(p.id) || (p.key && selectedPerms.has(p.key)))
                        ? 'Deselect All Actions'
                        : 'Select All Actions'}
                    </button>
                  </div>
                </div>
                <div className="max-h-72 overflow-y-auto space-y-4 pr-1 border border-slate-200 rounded-xl p-3 bg-slate-50/50">
                  {Object.keys(groupedPermissions).length === 0 ? (
                    <div className="text-center text-xs text-slate-400 py-4">No permissions available</div>
                  ) : (
                    Object.entries(groupedPermissions).map(([category, items]) => {
                      const allSelected = items.every((i) => selectedPerms.has(i.id) || (i.key && selectedPerms.has(i.key)));
                      const someSelected = items.some((i) => selectedPerms.has(i.id) || (i.key && selectedPerms.has(i.key)));

                      return (
                        <div key={category} className="space-y-2 bg-white p-3 rounded-xl border border-slate-200">
                          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                            <label className="flex items-center gap-2 cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={allSelected}
                                ref={(el) => {
                                  if (el) el.indeterminate = someSelected && !allSelected;
                                }}
                                onChange={() => toggleModulePermissions(category)}
                                className="h-4 w-4 text-indigo-600 rounded border-slate-300 focus:ring-indigo-500 cursor-pointer"
                              />
                              <span className="px-2.5 py-0.5 bg-indigo-50 text-indigo-700 font-bold rounded-md text-xs border border-indigo-100">
                                {category}
                              </span>
                              <span className="text-[11px] font-semibold text-slate-400">({items.length} permissions)</span>
                            </label>

                            <button
                              type="button"
                              onClick={() => toggleModulePermissions(category)}
                              className="text-[11px] font-bold text-indigo-600 hover:text-indigo-800 transition-colors cursor-pointer"
                            >
                              {allSelected ? 'Deselect All' : 'Select All'}
                            </button>
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                            {items.map((p) => {
                              const isChecked = selectedPerms.has(p.id) || (p.key ? selectedPerms.has(p.key) : false);
                              return (
                                <label
                                  key={p.id}
                                  className={`flex items-start justify-between p-2 rounded-lg border cursor-pointer transition-colors ${isChecked ? 'bg-indigo-50/50 border-indigo-200' : 'bg-slate-50/50 border-slate-200 hover:bg-slate-100/50'
                                    }`}
                                >
                                  <div className="space-y-0.5 pr-2">
                                    <span className="text-xs font-bold text-slate-900 block leading-tight">
                                      {p.name || p.key || 'Permission'}
                                    </span>
                                    {p.key && <span className="text-[10px] font-mono text-slate-500 block">{p.key}</span>}
                                    {p.description && (
                                      <span className="text-[10px] text-slate-400 block truncate max-w-[180px]">
                                        {p.description}
                                      </span>
                                    )}
                                  </div>
                                  <input
                                    type="checkbox"
                                    checked={isChecked}
                                    onChange={() => togglePermissionSelection(p)}
                                    className="h-4 w-4 text-indigo-600 rounded border-slate-300 focus:ring-indigo-500 mt-0.5 shrink-0"
                                  />
                                </label>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })
                  )}
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
                <label className="block text-xs font-semibold text-slate-700 mb-1">Select User Account *</label>
                <UserSelect
                  value={assignUserId}
                  onChange={setAssignUserId}
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

      {/* Create New Permission Modal */}
      {isPermModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex justify-between items-center pb-3 border-b border-slate-100">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <KeyRound className="w-5 h-5 text-emerald-600" />
                System Permissions Manager
              </h3>
              <button onClick={() => setIsPermModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Mode Switcher Tabs */}
            <div className="flex bg-slate-100 p-1 rounded-xl gap-1">
              <button
                type="button"
                onClick={() => setPermMode('single')}
                className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-colors cursor-pointer ${permMode === 'single' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-900'
                  }`}
              >
                Single Entry
              </button>
              <button
                type="button"
                onClick={() => setPermMode('json')}
                className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-colors cursor-pointer ${permMode === 'json' ? 'bg-white text-emerald-700 shadow-xs' : 'text-slate-500 hover:text-slate-900'
                  }`}
              >
                Upload JSON File
              </button>
            </div>

            {permMode === 'single' ? (
              <form onSubmit={handleCreatePermSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Permission Name *</label>
                  <input
                    type="text"
                    required
                    value={permName}
                    onChange={(e) => setPermName(e.target.value)}
                    placeholder="e.g. Export Financial Reports"
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Permission Action Key *</label>
                  <input
                    type="text"
                    required
                    value={permKey}
                    onChange={(e) => setPermKey(e.target.value)}
                    placeholder="e.g. reports:export"
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-emerald-500 font-mono"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Category / Module</label>
                    <select
                      value={permCategory}
                      onChange={(e) => setPermCategory(e.target.value)}
                      className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-emerald-500"
                    >
                      <option value="Leads">Leads</option>
                      <option value="Deals">Deals</option>
                      <option value="Contacts">Contacts</option>
                      <option value="Invoices">Invoices</option>
                      <option value="Reports">Reports</option>
                      <option value="Settings">Settings</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Description</label>
                    <input
                      type="text"
                      value={permDesc}
                      onChange={(e) => setPermDesc(e.target.value)}
                      placeholder="e.g. Allow downloading PDF/CSV"
                      className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-emerald-500"
                    />
                  </div>
                </div>

                <div className="flex justify-end gap-3 pt-2">
                  <button type="button" onClick={() => setIsPermModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={createPermMutation.isPending}
                    className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
                  >
                    {createPermMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    Create Permission
                  </button>
                </div>
              </form>
            ) : (
              <form onSubmit={handleBatchImportSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Upload permissions.json File</label>
                  <div className="border-2 border-dashed border-slate-300 hover:border-emerald-500 rounded-xl p-4 text-center bg-slate-50 transition-colors relative cursor-pointer">
                    <Upload className="w-6 h-6 text-emerald-600 mx-auto mb-1" />
                    <span className="text-xs font-semibold text-slate-700 block">
                      {jsonFileName ? `File selected: ${jsonFileName}` : 'Click or drop permissions.json here'}
                    </span>
                    <span className="text-[10px] text-slate-400 block">Supports standard permissions JSON array</span>
                    <input
                      type="file"
                      accept=".json,application/json"
                      onChange={handleFileUpload}
                      className="absolute inset-0 opacity-0 cursor-pointer"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Or Paste Permissions JSON Content</label>
                  <textarea
                    rows={6}
                    value={jsonText}
                    onChange={(e) => setJsonText(e.target.value)}
                    placeholder='[{"key": "users:read", "name": "View Users", "category": "Users", "description": "View users"}]'
                    className="w-full bg-slate-50 border border-slate-300 rounded-lg p-3 text-xs text-slate-900 font-mono outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>

                <div className="flex justify-end gap-3 pt-2">
                  <button type="button" onClick={() => setIsPermModalOpen(false)} className="px-4 py-2 text-xs font-semibold text-slate-600">
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={batchImportPermMutation.isPending || !jsonText.trim()}
                    className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
                  >
                    {batchImportPermMutation.isPending && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    Import JSON Permissions
                  </button>
                </div>
              </form>
            )}
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
