'use client';

import { getErrorMessage } from '@/lib/utils';
import React, { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  CheckSquare,
  Calendar,
  UserCheck,
  Edit,
  Trash2,
  Loader2,
  AlertCircle,
  X,
  CheckCircle2,
  Plus,
  CornerDownRight,
  Bell,
  User,
} from 'lucide-react';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { ModalShell } from '@/components/common/modal-shell';
import {
  useTaskQuery,
  useUpdateTaskMutation,
  useDeleteTaskMutation,
  useCompleteTaskMutation,
  useReopenTaskMutation,
  useSubtasksQuery,
  useAddSubtaskMutation,
  useAssignTaskMutation,
  useSetTaskReminderMutation,
  TaskUpdatePayload
} from '@/lib/api/tasks';
import { useUsersQuery } from '@/lib/api/users';

export default function TaskDetailPage() {
  const params = useParams();
  const router = useRouter();
  const taskId = (params?.id as string) || '';

  // Query Hooks
  const { data: task, isLoading, isError, refetch } = useTaskQuery(taskId);
  const { data: subtasks = [], refetch: refetchSubtasks } = useSubtasksQuery(taskId);
  const { data: users = [] } = useUsersQuery(1, 100);

  // Mutation Hooks
  const updateTaskMutation = useUpdateTaskMutation();
  const deleteTaskMutation = useDeleteTaskMutation();
  const completeTaskMutation = useCompleteTaskMutation();
  const reopenTaskMutation = useReopenTaskMutation();
  const addSubtaskMutation = useAddSubtaskMutation();
  const assignTaskMutation = useAssignTaskMutation();
  const setReminderMutation = useSetTaskReminderMutation();

  // State
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [newSubtaskTitle, setNewSubtaskTitle] = useState('');
  const [reminderTime, setReminderTime] = useState('');
  const [selectedUser, setSelectedUser] = useState('');

  // Form State for Editing
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState('Medium');
  const [status, setStatus] = useState('Pending');
  const [dueDate, setDueDate] = useState('');
  const [assignedTo, setAssignedTo] = useState('');

  // Toast notifications
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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

  const handleOpenEditModal = () => {
    if (!task) return;
    setTitle(task.title || '');
    setDescription(task.description || '');
    setPriority(task.priority || 'Medium');
    setStatus(task.status || 'Pending');
    setDueDate(task.due_date ? task.due_date.substring(0, 10) : '');
    setAssignedTo(task.assigned_to || '');
    setIsEditModalOpen(true);
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    const payload: TaskUpdatePayload = {
      title: title.trim(),
      description: description.trim() || undefined,
      priority,
      status,
      due_date: dueDate ? (dueDate.includes('T') ? dueDate : `${dueDate}T00:00:00Z`) : undefined,
      assigned_to: assignedTo.trim() || undefined,
    };

    try {
      await updateTaskMutation.mutateAsync({ id: taskId, payload });
      setSuccessMessage('Task updated successfully.');
      setIsEditModalOpen(false);
      refetch();
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to update task.'));
    }
  };

  const handleDeleteTask = async () => {
    try {
      await deleteTaskMutation.mutateAsync(taskId);
      router.push('/tasks');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to delete task.'));
    }
  };

  const handleToggleComplete = async () => {
    if (!task) return;
    try {
      if (task.status === 'Completed') {
        await reopenTaskMutation.mutateAsync(taskId);
        setSuccessMessage('Task reopened.');
      } else {
        await completeTaskMutation.mutateAsync(taskId);
        setSuccessMessage('Task marked as Completed.');
      }
      refetch();
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to update task status.'));
    }
  };

  const handleAddSubtaskSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSubtaskTitle.trim()) return;
    try {
      await addSubtaskMutation.mutateAsync({ taskId, title: newSubtaskTitle.trim() });
      setSuccessMessage(`Subtask "${newSubtaskTitle.trim()}" added.`);
      setNewSubtaskTitle('');
      refetchSubtasks();
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to add subtask.'));
    }
  };

  const handleAssignUserSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser) return;
    try {
      await assignTaskMutation.mutateAsync({ taskId, userId: selectedUser });
      setSuccessMessage('Task reassigned successfully.');
      setSelectedUser('');
      refetch();
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to assign user.'));
    }
  };

  const handleSetReminderSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reminderTime) return;
    try {
      await setReminderMutation.mutateAsync({ taskId, reminderTime });
      setSuccessMessage(`Automated reminder set for ${reminderTime}.`);
      setReminderTime('');
    } catch (err: unknown) {
      setErrorMessage(getErrorMessage(err, 'Failed to set reminder.'));
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-2 text-slate-500">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
          <span className="text-sm font-medium">Loading task details...</span>
        </div>
      </div>
    );
  }

  if (isError || !task) {
    return (
      <div className="p-6 max-w-2xl mx-auto space-y-4">
        <Link href="/tasks" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900 font-medium">
          <ArrowLeft className="w-4 h-4" />
          Back to Tasks
        </Link>
        <div className="p-6 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 space-y-2">
          <div className="flex items-center gap-2 font-bold text-base">
            <AlertCircle className="w-5 h-5 text-rose-600" />
            Task Not Found
          </div>
          <p className="text-sm">The task you requested could not be found or may have been deleted.</p>
        </div>
      </div>
    );
  }

  const s = task.status || 'Pending';
  const p = task.priority || 'Low';

  const badgeStyle =
    s === 'Completed'
      ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
      : s === 'In Progress'
      ? 'bg-amber-100 text-amber-800 border-amber-200'
      : 'bg-indigo-50 text-indigo-700 border-indigo-200';

  const priorityColor =
    p === 'High'
      ? 'bg-rose-100 text-rose-700 border-rose-200'
      : p === 'Medium'
      ? 'bg-amber-100 text-amber-700 border-amber-200'
      : 'bg-slate-100 text-slate-700 border-slate-200';

  return (
    <div className="space-y-6 w-full pb-12">
      {/* Navigation & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <Link href="/tasks" className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-indigo-600 transition-colors">
            <ArrowLeft className="w-4 h-4" />
            Back to Task List
          </Link>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-3">
            <CheckSquare className="w-6 h-6 text-indigo-600" />
            {task.title}
          </h1>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={handleToggleComplete}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold cursor-pointer transition-colors shadow-sm ${
              s === 'Completed'
                ? 'bg-amber-50 text-amber-700 border border-amber-300 hover:bg-amber-100'
                : 'bg-emerald-600 text-white hover:bg-emerald-700'
            }`}
          >
            <CheckCircle2 className="w-4 h-4" />
            {s === 'Completed' ? 'Reopen Task' : 'Mark Completed'}
          </button>

          <button
            onClick={handleOpenEditModal}
            className="flex items-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors shadow-sm cursor-pointer"
          >
            <Edit className="w-4 h-4 text-slate-500" />
            Edit Task
          </button>

          <button
            onClick={() => setIsDeleteModalOpen(true)}
            className="flex items-center gap-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 px-3.5 py-2 rounded-lg text-sm font-semibold transition-colors cursor-pointer"
          >
            <Trash2 className="w-4 h-4" />
            Delete
          </button>
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

      {/* Main Task Detail Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Overview & Description */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-6">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3">
              Task Overview
            </h3>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</span>
                <div>
                  <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${badgeStyle}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${s === 'Completed' ? 'bg-emerald-500' : s === 'In Progress' ? 'bg-amber-500' : 'bg-indigo-500'}`}></span>
                    {s}
                  </span>
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Priority</span>
                <div>
                  <span className={`px-2.5 py-1 rounded-md text-xs font-semibold border ${priorityColor}`}>
                    {p} Priority
                  </span>
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Due Date</span>
                <div className="flex items-center gap-1.5 text-slate-800 text-sm font-semibold">
                  <Calendar className="w-4 h-4 text-slate-400" />
                  <span>{task.due_date ? task.due_date.substring(0, 10) : 'No due date'}</span>
                </div>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-100">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1.5">Description</span>
              <p className="text-sm text-slate-700 bg-slate-50 p-4 rounded-xl border border-slate-200 min-h-[100px] leading-relaxed">
                {task.description || 'No description provided for this task.'}
              </p>
            </div>
          </div>

          {/* Subtasks Management */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3 flex items-center justify-between">
              <span>Sub-tasks ({subtasks.length})</span>
            </h3>

            <form onSubmit={handleAddSubtaskSubmit} className="flex gap-2">
              <input
                type="text"
                value={newSubtaskTitle}
                onChange={(e) => setNewSubtaskTitle(e.target.value)}
                placeholder="Add a new subtask..."
                className="flex-1 bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <button
                type="submit"
                disabled={addSubtaskMutation.isPending}
                className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer disabled:opacity-50"
              >
                <Plus className="w-4 h-4" />
                Add Subtask
              </button>
            </form>

            <div className="space-y-2 pt-1">
              {subtasks.length === 0 ? (
                <p className="text-xs text-slate-400 italic">No subtasks added yet.</p>
              ) : (
                subtasks.map((st) => (
                  <div key={st.id} className="flex items-center gap-2.5 text-xs text-slate-800 bg-slate-50 p-3 rounded-xl border border-slate-200">
                    <CornerDownRight className="w-4 h-4 text-indigo-500 shrink-0" />
                    <span className="font-medium">{st.title}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Assignee & Automated Reminder Controls */}
        <div className="space-y-6">
          {/* Assignment Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3 flex items-center gap-2">
              <UserCheck className="w-4 h-4 text-indigo-600" />
              Assigned Representative
            </h3>

            <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200">
              <div className="h-10 w-10 rounded-full bg-indigo-100 text-indigo-700 font-bold flex items-center justify-center text-sm">
                <User className="w-5 h-5" />
              </div>
              <div>
                <div className="font-semibold text-slate-900 text-sm">{getAssigneeName(task.assigned_to)}</div>
                <div className="text-xs text-slate-500">Representative</div>
              </div>
            </div>

            <form onSubmit={handleAssignUserSubmit} className="space-y-2 pt-2">
              <label className="block text-xs font-semibold text-slate-700">Reassign Task</label>
              <select
                value={selectedUser}
                onChange={(e) => setSelectedUser(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 text-slate-800 text-xs rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">Select Representative...</option>
                {users.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name} ({u.role || u.email})
                  </option>
                ))}
              </select>
              <button
                type="submit"
                disabled={!selectedUser || assignTaskMutation.isPending}
                className="w-full bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold py-2 rounded-lg cursor-pointer disabled:opacity-50"
              >
                Reassign Task
              </button>
            </form>
          </div>

          {/* Reminder Card */}
          <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider border-b border-slate-100 pb-3 flex items-center gap-2">
              <Bell className="w-4 h-4 text-amber-500" />
              Automated Reminder
            </h3>

            <form onSubmit={handleSetReminderSubmit} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Set Reminder Date & Time</label>
                <input
                  type="datetime-local"
                  value={reminderTime}
                  onChange={(e) => setReminderTime(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-xs text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <button
                type="submit"
                disabled={!reminderTime || setReminderMutation.isPending}
                className="w-full bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold py-2 rounded-lg cursor-pointer disabled:opacity-50 flex items-center justify-center gap-2"
              >
                <Bell className="w-3.5 h-3.5" />
                Schedule Notification
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* Edit Task Modal */}
      {isEditModalOpen && (
        <ModalShell
          isOpen={isEditModalOpen}
          onClose={() => setIsEditModalOpen(false)}
          size="lg"
          title={
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <CheckSquare className="w-5 h-5 text-indigo-600" />
              Edit Task
            </h2>
          }
        >
          <form onSubmit={handleSaveEdit} className="space-y-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">Task Title *</label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">Description</label>
              <textarea
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none resize-none"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">Priority</label>
                <select
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                >
                  <option value="Low">Low</option>
                  <option value="Medium">Medium</option>
                  <option value="High">High</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">Status</label>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                >
                  <option value="Pending">Pending</option>
                  <option value="In Progress">In Progress</option>
                  <option value="Completed">Completed</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">Due Date</label>
                <input
                  type="date"
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1">Assigned Representative</label>
                <input
                  type="text"
                  value={assignedTo}
                  onChange={(e) => setAssignedTo(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3.5 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-500 outline-none"
                />
              </div>
            </div>

            <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-3 pt-3 border-t border-slate-100">
              <button type="button" onClick={() => setIsEditModalOpen(false)} className="px-4 py-2 text-sm font-medium text-slate-600">
                Cancel
              </button>
              <button
                type="submit"
                disabled={updateTaskMutation.isPending}
                className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-lg font-medium text-sm cursor-pointer shadow-sm disabled:opacity-50"
              >
                {updateTaskMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                Save Changes
              </button>
            </div>
          </form>
        </ModalShell>
      )}

      {/* Delete Confirm Modal */}
      {isDeleteModalOpen && (
        <ConfirmModal
          isOpen={isDeleteModalOpen}
          title="Delete Task"
          description={`Are you sure you want to delete "${task.title}"? This action cannot be undone.`}
          confirmText="Delete Task"
          variant="danger"
          onConfirm={handleDeleteTask}
          onClose={() => setIsDeleteModalOpen(false)}
        />
      )}
    </div>
  );
}
