'use client';

import { ResponsiveSelect } from '@/components/common/responsive-select';

import { ActionMenu } from '@/components/common/action-menu';
import { getErrorMessage } from '@/lib/utils';
import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  CheckSquare,
  Calendar,
  AlertCircle,
  UserCheck,
  Plus,
  Filter,
  RotateCcw,
  Download,
  Upload,
  CheckCircle2,
  Trash2,
  Edit,
  ListTodo,
  X,
  Loader2,
  FileSpreadsheet,
} from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { ModalShell } from '@/components/common/modal-shell';
import { PermissionGate } from '@/components/common/permission-gate';
import { PERMISSIONS } from '@/lib/permissions';
import {
  useTasksQuery,
  useCreateTaskMutation,
  useUpdateTaskMutation,
  useDeleteTaskMutation,
  useCompleteTaskMutation,
  useReopenTaskMutation,
  useBulkDeleteTasksMutation,
  useBulkCompleteTasksMutation,
  exportTasksCsvApi,
  importTasksCsvApi,
  TaskItem,
  TaskCreatePayload,
} from '@/lib/api/tasks';
import { useUsersQuery } from '@/lib/api/users';

export default function TasksPage() {
  const router = useRouter();
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [priorityFilter, setPriorityFilter] = useState<string>('');
  const [page, setPage] = useState(1);
  const limit = 15;

  // Filter Popover State
  const [isFilterOpen, setIsFilterOpen] = useState(false);

  // Selection for bulk actions
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // Modal states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<TaskItem | null>(null);
  const [taskToDelete, setTaskToDelete] = useState<TaskItem | null>(null);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);

  // Form states for Create/Edit
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState('Medium');
  const [status, setStatus] = useState('Pending');
  const [dueDate, setDueDate] = useState('');
  const [assignedTo, setAssignedTo] = useState('');

  // Form states for Subtask & Reminder

  // Toast / Alert message state
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // CSV Import file state
  const [importFile, setImportFile] = useState<File | null>(null);
  const [isImporting, setIsImporting] = useState(false);

  // Debounce search input
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
      setPage(1);
    }, 250);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  // Reset page when filters change
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset pagination when filters change
    setPage(1);
  }, [statusFilter, priorityFilter]);

  // Query Hooks - connected to API with search, status, and priority query params
  const { data: tasks = [], isLoading: isTasksLoading, refetch: refetchTasks } = useTasksQuery({
    page,
    limit,
    search: debouncedSearchTerm || undefined,
    status: statusFilter || undefined,
    priority: priorityFilter || undefined,
  });

  const { data: users = [] } = useUsersQuery(1, 100);

  // Lookup assignee name
  const getAssigneeName = (userId?: string) => {
    if (!userId) return 'Unassigned';
    const matchedUser = users.find((u) => u.id === userId || u.email === userId || u.name === userId);
    if (matchedUser) return matchedUser.name;
    if (userId.length > 20 && userId.includes('-')) {
      return 'Sales Executive';
    }
    return userId;
  };

  // Mutation Hooks
  const createTaskMutation = useCreateTaskMutation();
  const updateTaskMutation = useUpdateTaskMutation();
  const deleteTaskMutation = useDeleteTaskMutation();
  const completeTaskMutation = useCompleteTaskMutation();
  const reopenTaskMutation = useReopenTaskMutation();
  const bulkDeleteMutation = useBulkDeleteTasksMutation();
  const bulkCompleteMutation = useBulkCompleteTasksMutation();

  // Reset modal form
  const resetForm = () => {
    setTitle('');
    setDescription('');
    setPriority('Medium');
    setStatus('Pending');
    setDueDate('');
    setAssignedTo('');
    setEditingTask(null);
  };

  const handleOpenCreateModal = () => {
    resetForm();
    setIsCreateModalOpen(true);
  };

  const handleOpenEditModal = (task: TaskItem) => {
    setEditingTask(task);
    setTitle(task.title || '');
    setDescription(task.description || '');
    setPriority(task.priority || 'Medium');
    setStatus(task.status || 'Pending');
    setDueDate(task.due_date ? task.due_date.substring(0, 10) : '');
    setAssignedTo(task.assigned_to || '');
    setIsCreateModalOpen(true);
  };

  const handleSaveTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setErrorMessage('Task title is required.');
      return;
    }
    setErrorMessage(null);

    const payload: TaskCreatePayload = {
      title: title.trim(),
      description: description.trim() || undefined,
      priority,
      status,
      due_date: dueDate ? (dueDate.includes('T') ? dueDate : `${dueDate}T00:00:00Z`) : undefined,
      assigned_to: assignedTo.trim() || undefined,
    };

    try {
      if (editingTask) {
        await updateTaskMutation.mutateAsync({ id: editingTask.id, payload });
        setSuccessMessage(`Task "${title}" updated successfully.`);
      } else {
        await createTaskMutation.mutateAsync(payload);
        setSuccessMessage(`Task "${title}" created successfully.`);
      }
      setIsCreateModalOpen(false);
      resetForm();
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to save task.'));
    }
  };

  const handleDeleteTask = async () => {
    if (!taskToDelete) return;
    try {
      await deleteTaskMutation.mutateAsync(taskToDelete.id);
      setSuccessMessage(`Task deleted successfully.`);
      setTaskToDelete(null);
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to delete task.'));
    }
  };

  const handleToggleComplete = async (task: TaskItem) => {
    try {
      if (task.status === 'Completed') {
        await reopenTaskMutation.mutateAsync(task.id);
        setSuccessMessage(`Task "${task.title}" reopened.`);
      } else {
        await completeTaskMutation.mutateAsync(task.id);
        setSuccessMessage(`Task "${task.title}" marked as Completed.`);
      }
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to update task status.'));
    }
  };

  // Bulk Actions
  const handleBulkComplete = async () => {
    if (selectedIds.size === 0) return;
    try {
      const res = await bulkCompleteMutation.mutateAsync(Array.from(selectedIds));
      setSuccessMessage(`${res.affected_count || selectedIds.size} task(s) marked complete.`);
      setSelectedIds(new Set());
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to complete selected tasks.'));
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    try {
      const res = await bulkDeleteMutation.mutateAsync(Array.from(selectedIds));
      setSuccessMessage(`${res.affected_count || selectedIds.size} task(s) deleted.`);
      setSelectedIds(new Set());
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to delete selected tasks.'));
    }
  };

  // Export CSV
  const handleExportCsv = async () => {
    try {
      const res = await exportTasksCsvApi();
      if (res.download_url) {
        window.open(res.download_url, '_blank');
      }
      setSuccessMessage('Tasks exported to CSV successfully.');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to export tasks.'));
    }
  };

  // Import CSV
  const handleImportCsvSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!importFile) {
      setErrorMessage('Please select a CSV file to import.');
      return;
    }
    setIsImporting(true);
    try {
      await importTasksCsvApi(importFile);
      setSuccessMessage('CSV import completed successfully.');
      setIsImportModalOpen(false);
      setImportFile(null);
      refetchTasks();
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to import CSV.'));
    } finally {
      setIsImporting(false);
    }
  };

  const activeFilterCount = (statusFilter ? 1 : 0) + (priorityFilter ? 1 : 0);

  // Table Columns Definition
  const columns: DataTableColumn<TaskItem>[] = [
    {
      id: 'title',
      header: 'TASK TITLE',
      cell: (item) => (
        <div className="flex items-center gap-3">
          <button
            onClick={(e) => {
              e.stopPropagation();
              handleToggleComplete(item);
            }}
            title={item.status === 'Completed' ? 'Reopen task' : 'Mark as Completed'}
            className={`flex h-7 w-7 items-center justify-center rounded-lg border transition-colors cursor-pointer ${
              item.status === 'Completed'
                ? 'bg-emerald-500 text-white border-emerald-500 hover:bg-emerald-600'
                : 'border-slate-300 text-slate-400 hover:border-indigo-500 hover:text-indigo-600 bg-white'
            }`}
          >
            <CheckSquare className="w-4 h-4" />
          </button>
          <div>
            <div
              onClick={(e) => {
                e.stopPropagation();
                router.push(`/tasks/${item.id}`);
              }}
              className={`font-semibold text-slate-900 hover:text-indigo-600 cursor-pointer transition-colors ${
                item.status === 'Completed' ? 'line-through text-slate-400' : ''
              }`}
            >
              {item.title}
            </div>
            {item.description && (
              <div className="text-xs text-slate-500 truncate max-w-xs">{item.description}</div>
            )}
          </div>
        </div>
      ),
    },
    {
      id: 'status',
      header: 'STATUS',
      cell: (item) => {
        const s = item.status || 'Pending';
        const badgeStyle =
          s === 'Completed'
            ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
            : s === 'In Progress'
            ? 'bg-amber-100 text-amber-800 border-amber-200'
            : 'bg-indigo-50 text-indigo-700 border-indigo-200';
        return (
          <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${badgeStyle}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${s === 'Completed' ? 'bg-emerald-500' : s === 'In Progress' ? 'bg-amber-500' : 'bg-indigo-500'}`}></span>
            {s}
          </span>
        );
      },
    },
    {
      id: 'priority',
      header: 'PRIORITY',
      cell: (item) => {
        const p = item.priority || 'Low';
        const badgeColor =
          p === 'High'
            ? 'bg-rose-100 text-rose-700 border-rose-200'
            : p === 'Medium'
            ? 'bg-amber-100 text-amber-700 border-amber-200'
            : 'bg-slate-100 text-slate-700 border-slate-200';
        return (
          <span className={`px-2.5 py-0.5 rounded-md text-xs font-semibold border ${badgeColor}`}>
            {p}
          </span>
        );
      },
    },
    {
      id: 'due_date',
      header: 'DUE DATE',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-medium">
          <Calendar className="w-3.5 h-3.5 text-slate-400" />
          <span>{item.due_date ? item.due_date.substring(0, 10) : 'No due date'}</span>
        </div>
      ),
    },
    {
      id: 'assigned_to',
      header: 'ASSIGNED TO',
      cell: (item) => (
        <div className="flex items-center gap-1.5 text-slate-700 text-xs font-medium">
          <UserCheck className="w-3.5 h-3.5 text-slate-400" />
          <span className="truncate max-w-[160px] font-semibold">{getAssigneeName(item.assigned_to)}</span>
        </div>
      ),
    },
    {
      id: 'actions',
      header: 'ACTIONS',
      cell: (item) => (
        <ActionMenu
          iconOnly
          label="Open task actions"
          onTriggerClick={(event) => event.stopPropagation()}
          actions={[
            { label: 'View details & subtasks', icon: <ListTodo className="w-4 h-4 text-indigo-600" />, onSelect: () => router.push(`/tasks/${item.id}`) },
            { label: 'Edit task', icon: <Edit className="w-4 h-4 text-blue-600" />, onSelect: () => handleOpenEditModal(item) },
            { label: 'Delete task', icon: <Trash2 className="w-4 h-4" />, variant: 'destructive', onSelect: () => setTaskToDelete(item) },
          ]}
        />
      ),
    },
  ];

  // Combined Single Filter Popover Button Element inside DataTable Header Toolbar (Right Side)
  const singleFilterPopover = (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setIsFilterOpen(!isFilterOpen)}
        className={`h-9 px-3 py-1 rounded-lg border text-xs font-bold inline-flex items-center gap-1.5 cursor-pointer transition-colors ${
          activeFilterCount > 0
            ? 'bg-indigo-50 border-indigo-300 text-indigo-700 font-semibold'
            : 'bg-slate-50 hover:bg-slate-100 border-slate-300 text-slate-900'
        }`}
      >
        <Filter className="h-3.5 w-3.5 text-slate-500" />
        <span>Filter</span>
        {activeFilterCount > 0 && (
          <span className="w-4.5 h-4.5 rounded-full bg-indigo-600 text-white text-[10px] font-bold flex items-center justify-center">
            {activeFilterCount}
          </span>
        )}
      </button>

      {/* Popover Dropdown Menu Right-aligned over the table */}
      {isFilterOpen && (
        <div className="absolute right-0 mt-2 w-64 bg-white rounded-xl shadow-2xl border border-slate-200 p-4 z-50 space-y-4 animate-in fade-in zoom-in-95 duration-100">
          <div className="flex items-center justify-between pb-2 border-b border-slate-100">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">Filter Tasks</h4>
            {activeFilterCount > 0 && (
              <button
                type="button"
                onClick={() => {
                  setStatusFilter('');
                  setPriorityFilter('');
                }}
                className="text-xs text-indigo-600 hover:underline font-semibold flex items-center gap-1 cursor-pointer"
              >
                <RotateCcw className="w-3 h-3" />
                Reset
              </button>
            )}
          </div>

          {/* Status Dropdown */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">Status</label>
            <ResponsiveSelect
              value={statusFilter}
              onValueChange={setStatusFilter}
              className="w-full bg-slate-50 border border-slate-300 text-slate-800 text-xs rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">All Statuses</option>
              <option value="Pending">Pending</option>
              <option value="In Progress">In Progress</option>
              <option value="Completed">Completed</option>
            </ResponsiveSelect>
          </div>

          {/* Priority Dropdown */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">Priority</label>
            <ResponsiveSelect
              value={priorityFilter}
              onValueChange={setPriorityFilter}
              className="w-full bg-slate-50 border border-slate-300 text-slate-800 text-xs rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">All Priorities</option>
              <option value="High">High Priority</option>
              <option value="Medium">Medium Priority</option>
              <option value="Low">Low Priority</option>
            </ResponsiveSelect>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Toast Notifications */}
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

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <CheckSquare className="w-7 h-7 text-indigo-600" />
            Task Management
          </h1>
          <p className="text-slate-500 text-sm mt-0.5">Assign, prioritize, schedule, and track sales representative tasks</p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={() => setIsImportModalOpen(true)}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3.5 py-2 rounded-lg font-medium text-sm transition-colors shadow-sm cursor-pointer"
          >
            <Upload className="w-4 h-4 text-slate-500" />
            Import CSV
          </button>

          <button
            onClick={handleExportCsv}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3.5 py-2 rounded-lg font-medium text-sm transition-colors shadow-sm cursor-pointer"
          >
            <Download className="w-4 h-4 text-slate-500" />
            Export CSV
          </button>

          <PermissionGate permission={PERMISSIONS.TASKS.CREATE}>
            <button
              onClick={handleOpenCreateModal}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium text-sm transition-colors shadow-sm cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              Create Task
            </button>
          </PermissionGate>
        </div>
      </div>



      {/* Main Data Table with Filter Button on the Right Side & Row Click Detail Navigation */}
      <DataTable<TaskItem>
        columns={columns}
        data={tasks}
        getRowKey={(item) => item.id}
        onRowClick={(item) => router.push(`/tasks/${item.id}`)}
        emptyTitle="No tasks found"
        emptyDescription="Try clearing search or filter parameters to view tasks."
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search task title..."
        hasActiveFilters={activeFilterCount > 0}
        onClearFilters={() => {
          setStatusFilter('');
          setPriorityFilter('');
        }}
        toolbarActions={
          <div className="flex items-center gap-2">
            {selectedIds.size > 0 && (
              <div className="flex w-full flex-wrap items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1 sm:w-auto">
                <span className="text-xs font-semibold text-indigo-700">{selectedIds.size} selected</span>
                <PermissionGate permission={PERMISSIONS.TASKS.COMPLETE}>
                  <button
                    onClick={handleBulkComplete}
                    className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-xs font-semibold cursor-pointer"
                  >
                    Bulk Complete
                  </button>
                </PermissionGate>
                <PermissionGate permission={PERMISSIONS.TASKS.DELETE}>
                  <button
                    onClick={handleBulkDelete}
                    className="px-2.5 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded text-xs font-semibold cursor-pointer"
                  >
                    Bulk Delete
                  </button>
                </PermissionGate>
              </div>
            )}
            {singleFilterPopover}
          </div>
        }
        isLoading={isTasksLoading}
        pagination={{
          pageIndex: page - 1,
          pageCount: tasks.length >= limit ? page + 1 : page,
          onPageChange: (p) => setPage(p + 1),
          totalRecords: (page - 1) * limit + tasks.length,
        }}
      />

      {/* Create / Edit Task Modal */}
      <ModalShell
        isOpen={isCreateModalOpen}
        onClose={() => {
          setIsCreateModalOpen(false);
          resetForm();
        }}
        size="lg"
        title={
          <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <CheckSquare className="w-5 h-5 text-indigo-600" />
            {editingTask ? 'Edit Task' : 'Create New Task'}
          </h2>
        }
      >
        <form onSubmit={handleSaveTask} className="space-y-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
              Task Title *
            </label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Schedule Product Demo with Client"
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
              Description
            </label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Detailed notes or specific outcome requirements..."
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none resize-none"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                Priority Level
              </label>
              <ResponsiveSelect
                value={priority}
                onValueChange={setPriority}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
              >
                <option value="Low">Low</option>
                <option value="Medium">Medium</option>
                <option value="High">High</option>
              </ResponsiveSelect>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                Status
              </label>
              <ResponsiveSelect
                value={status}
                onValueChange={setStatus}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
              >
                <option value="Pending">Pending</option>
                <option value="In Progress">In Progress</option>
                <option value="Completed">Completed</option>
              </ResponsiveSelect>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                Due Date
              </label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">
                Assigned Representative
              </label>
              <input
                type="text"
                value={assignedTo}
                onChange={(e) => setAssignedTo(e.target.value)}
                placeholder="e.g. Representative"
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
              />
            </div>
          </div>

          <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={() => {
                setIsCreateModalOpen(false);
                resetForm();
              }}
              className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createTaskMutation.isPending || updateTaskMutation.isPending}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-lg font-medium text-sm cursor-pointer shadow-sm disabled:opacity-50"
            >
              {(createTaskMutation.isPending || updateTaskMutation.isPending) && (
                <Loader2 className="w-4 h-4 animate-spin" />
              )}
              {editingTask ? 'Save Changes' : 'Create Task'}
            </button>
          </div>
        </form>
      </ModalShell>

      {/* CSV Import Modal */}
      <ModalShell
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        size="md"
        title={
          <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <FileSpreadsheet className="w-5 h-5 text-indigo-600" />
            Import Tasks from CSV
          </h3>
        }
      >
        <form onSubmit={handleImportCsvSubmit} className="space-y-4">
          <div className="border-2 border-dashed border-slate-300 rounded-xl p-6 text-center space-y-2 hover:border-indigo-400 transition-colors">
            <Upload className="w-8 h-8 text-slate-400 mx-auto" />
            <p className="text-xs text-slate-600 font-medium">Select a CSV file containing task headers (title, priority, due_date, status)</p>
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setImportFile(e.target.files?.[0] || null)}
              className="block w-full text-xs text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100 cursor-pointer"
            />
          </div>

          <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-2 sm:gap-3 pt-2">
            <button
              type="button"
              onClick={() => setIsImportModalOpen(false)}
              className="px-4 py-2 text-xs font-semibold text-slate-600 cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isImporting || !importFile}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
            >
              {isImporting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Upload & Import
            </button>
          </div>
        </form>
      </ModalShell>

      {/* Confirm Task Delete Modal */}
      {taskToDelete && (
        <ConfirmModal
          isOpen={!!taskToDelete}
          title="Delete Task"
          description={`Are you sure you want to delete "${taskToDelete.title}"? This action cannot be undone.`}
          confirmText="Delete"
          variant="danger"
          onConfirm={handleDeleteTask}
          onClose={() => setTaskToDelete(null)}
        />
      )}
    </div>
  );
}
