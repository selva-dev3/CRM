'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, CalendarDays, CircleDollarSign, FolderKanban, Trash2, UserRound } from 'lucide-react';

import { ConfirmModal } from '@/components/common/confirm-modal';
import { PermissionGate } from '@/components/common/permission-gate';
import { Button } from '@/components/ui/button';
import { useDeleteProjectMutation, useProjectQuery } from '@/lib/api/projects';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';
import { useState } from 'react';

export default function ProjectDetailPage(): React.JSX.Element {
  const params = useParams();
  const router = useRouter();
  const projectId = String(params?.id ?? '');
  const projectQuery = useProjectQuery(projectId);
  const deleteProject = useDeleteProjectMutation();
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (projectQuery.isLoading) return <div className="p-8 text-sm text-slate-500">Loading project…</div>;
  if (projectQuery.isError || !projectQuery.data) return <div className="space-y-4 p-6"><Link href="/projects" className="inline-flex items-center gap-2 text-sm text-blue-600"><ArrowLeft className="size-4" />Back to Projects</Link><div className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-rose-800">Project not found or no longer accessible.</div></div>;

  const project = projectQuery.data;
  const remove = async () => {
    try {
      await deleteProject.mutateAsync(project.id);
      router.push('/projects');
    } catch (reason) {
      setError(getErrorMessage(reason, 'Unable to delete project.'));
      setConfirmingDelete(false);
    }
  };

  return <div className="space-y-6 pb-12">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
      <div><Link href="/projects" className="mb-3 inline-flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-blue-600"><ArrowLeft className="size-4" />Back to Projects</Link><h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900"><FolderKanban className="size-7 text-blue-600" />{project.name}</h1><p className="mt-2 max-w-3xl text-sm text-slate-600">{project.description || 'No project description.'}</p></div>
      <PermissionGate permission={PERMISSIONS.PROJECTS.DELETE}><Button variant="destructive" onClick={() => setConfirmingDelete(true)}><Trash2 className="size-4" />Delete</Button></PermissionGate>
    </div>
    {error && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <article className="rounded-xl border bg-white p-5"><p className="text-xs font-semibold uppercase text-slate-500">Status</p><p className="mt-2 font-semibold text-slate-900">{project.status}</p></article>
      <article className="rounded-xl border bg-white p-5"><p className="text-xs font-semibold uppercase text-slate-500">Priority</p><p className="mt-2 font-semibold text-slate-900">{project.priority}</p></article>
      <article className="rounded-xl border bg-white p-5"><p className="flex items-center gap-1 text-xs font-semibold uppercase text-slate-500"><CircleDollarSign className="size-4" />Budget</p><p className="mt-2 font-semibold text-slate-900">{project.budget == null ? 'Not set' : project.budget.toLocaleString()}</p></article>
      <article className="rounded-xl border bg-white p-5"><p className="flex items-center gap-1 text-xs font-semibold uppercase text-slate-500"><UserRound className="size-4" />Owner</p><p className="mt-2 break-all font-semibold text-slate-900">{project.owner_id || 'Unassigned'}</p></article>
    </div>
    <section className="rounded-xl border bg-white p-6"><div className="mb-3 flex items-center justify-between"><h2 className="font-semibold text-slate-900">Delivery progress</h2><span className="text-sm font-semibold text-blue-700">{project.completion_percentage}%</span></div><div className="h-3 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-blue-600" style={{ width: `${project.completion_percentage}%` }} /></div><div className="mt-5 grid gap-4 sm:grid-cols-2"><div><p className="flex items-center gap-1 text-xs font-semibold uppercase text-slate-500"><CalendarDays className="size-4" />Start date</p><p className="mt-1 text-sm text-slate-900">{project.start_date ? new Date(project.start_date).toLocaleDateString() : 'Not set'}</p></div><div><p className="flex items-center gap-1 text-xs font-semibold uppercase text-slate-500"><CalendarDays className="size-4" />Due date</p><p className="mt-1 text-sm text-slate-900">{project.due_date ? new Date(project.due_date).toLocaleDateString() : 'Not set'}</p></div></div></section>
    <ConfirmModal isOpen={confirmingDelete} onClose={() => setConfirmingDelete(false)} onConfirm={remove} title="Delete project" message={`Delete “${project.name}”? Linked deals and tasks will retain their records but lose this association.`} confirmText="Delete Project" variant="danger" isLoading={deleteProject.isPending} />
  </div>;
}
