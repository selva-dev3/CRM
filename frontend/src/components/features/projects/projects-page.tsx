'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { FolderKanban, Pencil, Plus, Trash2 } from 'lucide-react';

import { ActionMenu } from '@/components/common/action-menu';
import { ConfirmModal } from '@/components/common/confirm-modal';
import { DataTable, type DataTableColumn } from '@/components/common/data-table';
import { DatePicker } from '@/components/common/date-picker';
import { ModalShell } from '@/components/common/modal-shell';
import { PermissionGate } from '@/components/common/permission-gate';
import { ResponsiveSelect } from '@/components/common/responsive-select';
import { UserSelect } from '@/components/common/user-select';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { useHasPermission } from '@/hooks/use-has-permission';
import {
  type ProjectItem,
  type ProjectPayload,
  useCreateProjectMutation,
  useDeleteProjectMutation,
  useProjectsPageQuery,
  useUpdateProjectMutation,
} from '@/lib/api/projects';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';

const STATUSES = ['Planning', 'Active', 'On Hold', 'Completed', 'Cancelled'] as const;
const PRIORITIES = ['Low', 'Medium', 'High', 'Critical'] as const;

const EMPTY_FORM: ProjectPayload = {
  name: '',
  description: '',
  status: 'Planning',
  priority: 'Medium',
  owner_id: null,
  start_date: null,
  due_date: null,
  budget: null,
  completion_percentage: 0,
};

function badgeClass(value: string): string {
  if (value === 'Completed') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (value === 'Active' || value === 'High' || value === 'Critical') return 'border-blue-200 bg-blue-50 text-blue-700';
  if (value === 'Cancelled') return 'border-rose-200 bg-rose-50 text-rose-700';
  return 'border-slate-200 bg-slate-50 text-slate-700';
}

export default function ProjectsPage(): React.JSX.Element {
  const router = useRouter();
  const { hasPermission } = useHasPermission();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [editingProject, setEditingProject] = useState<ProjectItem | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [projectToDelete, setProjectToDelete] = useState<ProjectItem | null>(null);
  const [form, setForm] = useState<ProjectPayload>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const limit = 15;

  const projectsQuery = useProjectsPageQuery({
    page,
    limit,
    status: statusFilter || undefined,
    priority: priorityFilter || undefined,
  });
  const createProject = useCreateProjectMutation();
  const updateProject = useUpdateProjectMutation();
  const deleteProject = useDeleteProjectMutation();
  const projects = projectsQuery.data?.items ?? [];
  const total = projectsQuery.data?.total ?? 0;
  const canSelectOwner = hasPermission(PERMISSIONS.PROJECTS.ASSIGN)
    && hasPermission(PERMISSIONS.USERS.READ);

  const openCreate = () => {
    setEditingProject(null);
    setForm({ ...EMPTY_FORM });
    setIsFormOpen(true);
    setError(null);
  };

  const closeForm = () => {
    setEditingProject(null);
    setForm(EMPTY_FORM);
    setIsFormOpen(false);
  };

  const openEdit = (project: ProjectItem) => {
    setEditingProject(project);
    setIsFormOpen(true);
    setForm({
      name: project.name,
      description: project.description ?? '',
      status: project.status,
      priority: project.priority,
      owner_id: project.owner_id ?? null,
      start_date: project.start_date?.slice(0, 10) ?? null,
      due_date: project.due_date?.slice(0, 10) ?? null,
      budget: project.budget ?? null,
      completion_percentage: project.completion_percentage,
    });
    setError(null);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.name.trim()) {
      setError('Project name is required.');
      return;
    }
    if (form.start_date && form.due_date && form.due_date < form.start_date) {
      setError('Due date must be on or after the start date.');
      return;
    }
    const payload: ProjectPayload = {
      ...form,
      name: form.name.trim(),
      description: form.description?.trim() || null,
    };
    if (!canSelectOwner) delete payload.owner_id;
    try {
      if (editingProject) {
        await updateProject.mutateAsync({ id: editingProject.id, payload });
        setSuccess('Project updated successfully.');
      } else {
        await createProject.mutateAsync(payload);
        setSuccess('Project created successfully.');
      }
      closeForm();
    } catch (reason) {
      setError(getErrorMessage(reason, 'Unable to save project.'));
    }
  };

  const confirmDelete = async () => {
    if (!projectToDelete) return;
    try {
      await deleteProject.mutateAsync(projectToDelete.id);
      if (projects.length === 1 && page > 1) setPage((current) => current - 1);
      setSuccess('Project deleted successfully.');
      setProjectToDelete(null);
    } catch (reason) {
      setError(getErrorMessage(reason, 'Unable to delete project.'));
    }
  };

  const columns: DataTableColumn<ProjectItem>[] = [
    {
      id: 'name',
      header: 'PROJECT',
      cell: (project) => <div><p className="font-semibold text-slate-900">{project.name}</p><p className="max-w-80 truncate text-xs text-slate-500">{project.description || 'No description'}</p></div>,
    },
    { id: 'status', header: 'STATUS', cell: (project) => <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${badgeClass(project.status)}`}>{project.status}</span> },
    { id: 'priority', header: 'PRIORITY', cell: (project) => <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${badgeClass(project.priority)}`}>{project.priority}</span> },
    { id: 'progress', header: 'PROGRESS', cell: (project) => <div className="min-w-28"><div className="mb-1 flex justify-between text-xs"><span>{project.completion_percentage}%</span></div><div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-blue-600" style={{ width: `${project.completion_percentage}%` }} /></div></div> },
    { id: 'due', header: 'DUE DATE', cell: (project) => project.due_date ? new Date(project.due_date).toLocaleDateString() : 'Not set' },
    {
      id: 'actions',
      header: 'ACTIONS',
      cell: (project) => <ActionMenu iconOnly label="Open project actions" onTriggerClick={(event) => event.stopPropagation()} actions={[
        { label: 'Edit project', permission: PERMISSIONS.PROJECTS.UPDATE, icon: <Pencil className="size-4" />, onSelect: () => openEdit(project) },
        { label: 'Delete project', permission: PERMISSIONS.PROJECTS.DELETE, icon: <Trash2 className="size-4" />, variant: 'destructive', onSelect: () => setProjectToDelete(project) },
      ]} />,
    },
  ];

  return <div className="space-y-6 pb-12">
    {(error || success) && <div role="status" className={`rounded-xl border p-4 text-sm ${error ? 'border-rose-200 bg-rose-50 text-rose-800' : 'border-emerald-200 bg-emerald-50 text-emerald-800'}`}>{error || success}</div>}
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
      <div><h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900"><FolderKanban className="size-7 text-blue-600" />Projects</h1><p className="mt-1 text-sm text-slate-500">Plan and track organization projects, ownership, budget, and delivery progress.</p></div>
      <PermissionGate permission={PERMISSIONS.PROJECTS.CREATE}><Button onClick={openCreate} className="w-full gap-2 sm:w-auto"><Plus className="size-4" />Create Project</Button></PermissionGate>
    </div>
    <DataTable
      columns={columns}
      data={projects}
      getRowKey={(project) => project.id}
      onRowClick={(project) => router.push(`/projects/${project.id}`)}
      emptyTitle="No projects found"
      emptyDescription="Create a project or adjust the current filters."
      filters={[
        { label: 'Status', value: statusFilter, onChange: (value) => { setStatusFilter(value); setPage(1); }, options: STATUSES.map((value) => ({ label: value, value })) },
        { label: 'Priority', value: priorityFilter, onChange: (value) => { setPriorityFilter(value); setPage(1); }, options: PRIORITIES.map((value) => ({ label: value, value })) },
      ]}
      hasActiveFilters={Boolean(statusFilter || priorityFilter)}
      onClearFilters={() => { setStatusFilter(''); setPriorityFilter(''); setPage(1); }}
      isLoading={projectsQuery.isLoading}
      pagination={{ pageIndex: page - 1, pageCount: Math.max(1, Math.ceil(total / limit)), onPageChange: (value) => setPage(value + 1), totalRecords: total }}
    />

    <ModalShell isOpen={isFormOpen} onClose={closeForm} size="lg" title={editingProject ? 'Edit Project' : 'Create Project'}>
      <form onSubmit={submit} className="space-y-4">
        <div><label htmlFor="project-name" className="mb-1 block text-xs font-semibold">Project name *</label><Input id="project-name" required maxLength={255} value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} /></div>
        <div><label htmlFor="project-description" className="mb-1 block text-xs font-semibold">Description</label><Textarea id="project-description" value={form.description ?? ''} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} /></div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div><label className="mb-1 block text-xs font-semibold">Status</label><ResponsiveSelect value={form.status ?? 'Planning'} onValueChange={(value) => setForm((current) => ({ ...current, status: value }))}>{STATUSES.map((value) => <option key={value}>{value}</option>)}</ResponsiveSelect></div>
          <div><label className="mb-1 block text-xs font-semibold">Priority</label><ResponsiveSelect value={form.priority ?? 'Medium'} onValueChange={(value) => setForm((current) => ({ ...current, priority: value }))}>{PRIORITIES.map((value) => <option key={value}>{value}</option>)}</ResponsiveSelect></div>
          <div><label className="mb-1 block text-xs font-semibold">Start date</label><DatePicker value={form.start_date ?? ''} onValueChange={(value) => setForm((current) => ({ ...current, start_date: value || null }))} /></div>
          <div><label className="mb-1 block text-xs font-semibold">Due date</label><DatePicker value={form.due_date ?? ''} onValueChange={(value) => setForm((current) => ({ ...current, due_date: value || null }))} /></div>
          <div><label htmlFor="project-budget" className="mb-1 block text-xs font-semibold">Budget</label><Input id="project-budget" type="number" min="0" step="0.01" value={form.budget ?? ''} onChange={(event) => setForm((current) => ({ ...current, budget: event.target.value === '' ? null : Number(event.target.value) }))} /></div>
          <div><label htmlFor="project-progress" className="mb-1 block text-xs font-semibold">Completion percentage</label><Input id="project-progress" type="number" min="0" max="100" value={form.completion_percentage ?? 0} onChange={(event) => setForm((current) => ({ ...current, completion_percentage: Number(event.target.value) }))} /></div>
        </div>
        {canSelectOwner && <div><label className="mb-1 block text-xs font-semibold">Owner</label><UserSelect value={form.owner_id ?? ''} onChange={(value) => setForm((current) => ({ ...current, owner_id: value || null }))} /></div>}
        <div className="flex flex-col-reverse justify-end gap-2 border-t pt-4 sm:flex-row"><Button type="button" variant="outline" onClick={closeForm}>Cancel</Button><Button type="submit" disabled={createProject.isPending || updateProject.isPending}>{editingProject ? 'Save Changes' : 'Create Project'}</Button></div>
      </form>
    </ModalShell>
    <ConfirmModal isOpen={Boolean(projectToDelete)} onClose={() => setProjectToDelete(null)} onConfirm={confirmDelete} title="Delete project" message={`Delete “${projectToDelete?.name ?? ''}”? Linked deals and tasks will remain but lose this project association.`} confirmText="Delete Project" variant="danger" isLoading={deleteProject.isPending} />
  </div>;
}
