'use client';

import { useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Flag, Plus, Trash2 } from 'lucide-react';

import { ModuleError, PageNavigator } from '@/components/common/module-page-state';
import { ModalShell } from '@/components/common/modal-shell';
import { Button } from '@/components/ui/button';
import { useHasPermission } from '@/hooks/use-has-permission';
import { useCreateMilestone, useDeleteMilestone, useMilestonesQuery, useUpdateMilestone } from '@/lib/api/milestones';
import { useProjectQuery, useProjectsPageQuery } from '@/lib/api/projects';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';

const LIMIT = 20;

export default function MilestonesPage() {
  const searchParams = useSearchParams();
  const { hasPermission } = useHasPermission();
  const [projectId, setProjectId] = useState(() => searchParams.get('project_id') ?? '');
  const [projectSearch, setProjectSearch] = useState('');
  const [page, setPage] = useState(1);
  const [name, setName] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [error, setError] = useState('');
  const projects = useProjectsPageQuery({ page: 1, limit: 50, search: projectSearch || undefined });
  const selectedProject = useProjectQuery(projectId);
  const projectOptions = projects.data?.items ?? [];
  const selectedProjectIsHidden = Boolean(
    selectedProject.data && !projectOptions.some((project) => project.id === projectId),
  );
  const milestones = useMilestonesQuery({ page, limit: LIMIT, project_id: projectId || undefined });
  const create = useCreateMilestone();
  const update = useUpdateMilestone();
  const remove = useDeleteMilestone();

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!projectId || !name.trim()) return setError('Select a project and enter a milestone name.');
    try {
      await create.mutateAsync({ project_id: projectId, name: name.trim(), due_date: dueDate || undefined });
      setName(''); setDueDate(''); setError(''); setIsCreateOpen(false);
    } catch (reason) { setError(getErrorMessage(reason, 'Could not create milestone.')); }
  }

  async function runAction(action: () => Promise<unknown>, fallback: string) {
    try { await action(); setError(''); }
    catch (reason) { setError(getErrorMessage(reason, fallback)); }
  }

  return <div className="space-y-6 pb-12">
    <header className="flex flex-wrap items-center justify-between gap-3"><div><h1 className="flex items-center gap-2 text-2xl font-bold"><Flag className="text-indigo-600" />Milestones</h1><p className="mt-1 text-sm text-slate-500">Track delivery dates and project outcomes.</p></div>{hasPermission(PERMISSIONS.PROJECTS.CREATE) && <Button onClick={() => { setError(''); setIsCreateOpen(true); }}><Plus />Create milestone</Button>}</header>
    <div className="grid gap-3 rounded-xl border bg-white p-4 sm:grid-cols-2"><input aria-label="Search projects" className="h-10 rounded-lg border px-3" placeholder="Search projects…" value={projectSearch} onChange={(event) => setProjectSearch(event.target.value)} /><select aria-label="Filter milestones by project" className="h-10 rounded-lg border px-3" value={projectId} onChange={(event) => { setProjectId(event.target.value); setPage(1); }}><option value="">All projects</option>{selectedProjectIsHidden && <option value={selectedProject.data!.id}>{selectedProject.data!.name}</option>}{projectOptions.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></div>
    {projects.isError && <ModuleError message="Projects could not be loaded." retry={() => projects.refetch()} />}
    {error && <ModuleError message={error}/>} {milestones.isError && <ModuleError message="Milestones could not be loaded." retry={() => milestones.refetch()} />}
    <div className="overflow-x-auto rounded-xl border bg-white"><table className="min-w-full text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="p-4">Milestone</th><th className="p-4">Project</th><th className="p-4">Due</th><th className="p-4">Status</th><th className="p-4">Actions</th></tr></thead><tbody>{milestones.data?.items.map((milestone) => <tr className="border-t" key={milestone.id}><td className="p-4 font-semibold">{milestone.name}</td><td className="p-4">{projects.data?.items.find((project) => project.id === milestone.project_id)?.name ?? milestone.project_id}</td><td className="p-4">{milestone.due_date?.slice(0,10) ?? '—'}</td><td className="p-4">{milestone.status}</td><td className="p-4"><div className="flex gap-3">{hasPermission(PERMISSIONS.PROJECTS.UPDATE) && milestone.status === 'Pending' && <button disabled={update.isPending} className="text-indigo-600 disabled:opacity-50" onClick={() => runAction(() => update.mutateAsync({ id: milestone.id, payload: { status: 'Completed' } }), 'Could not complete milestone.')}>Complete</button>}{hasPermission(PERMISSIONS.PROJECTS.DELETE) && <button disabled={remove.isPending} aria-label={`Delete ${milestone.name}`} className="text-rose-600 disabled:opacity-50" onClick={() => runAction(() => remove.mutateAsync(milestone.id), 'Could not delete milestone.')}><Trash2 size={16}/></button>}</div></td></tr>)}</tbody></table>{milestones.isLoading && <p className="p-8 text-center text-slate-500">Loading milestones…</p>}{!milestones.isLoading && !milestones.isError && !milestones.data?.items.length && <p className="p-8 text-center text-slate-500">No milestones found.</p>}<PageNavigator page={page} total={milestones.data?.total ?? 0} limit={LIMIT} onChange={setPage}/></div>
    <ModalShell isOpen={isCreateOpen} onClose={() => !create.isPending && setIsCreateOpen(false)} title="Create milestone" footer={<><Button type="button" variant="outline" disabled={create.isPending} onClick={() => setIsCreateOpen(false)}>Cancel</Button><Button form="milestone-create-form" disabled={create.isPending}>{create.isPending ? 'Creating…' : 'Create milestone'}</Button></>}><form id="milestone-create-form" onSubmit={submit} className="space-y-4 py-4"><div><label htmlFor="milestone-project" className="mb-1 block text-sm font-medium">Project</label><select id="milestone-project" required className="h-10 w-full rounded-lg border px-3" value={projectId} onChange={(event) => { setProjectId(event.target.value); setPage(1); }}><option value="">Select project</option>{selectedProjectIsHidden && <option value={selectedProject.data!.id}>{selectedProject.data!.name}</option>}{projectOptions.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></div><div><label htmlFor="milestone-name" className="mb-1 block text-sm font-medium">Milestone name</label><input id="milestone-name" autoFocus required className="h-10 w-full rounded-lg border px-3" value={name} onChange={(event) => setName(event.target.value)} /></div><div><label htmlFor="milestone-due-date" className="mb-1 block text-sm font-medium">Due date</label><input id="milestone-due-date" type="date" className="h-10 w-full rounded-lg border px-3" value={dueDate} onChange={(event) => setDueDate(event.target.value)} /></div>{error && <p role="alert" className="text-sm text-rose-700">{error}</p>}</form></ModalShell>
  </div>;
}
