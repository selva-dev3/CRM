'use client';

import { useState } from 'react';
import { Flag, Plus, Trash2 } from 'lucide-react';

import { ModuleError, PageNavigator } from '@/components/common/module-page-state';
import { useHasPermission } from '@/hooks/use-has-permission';
import { useCreateMilestone, useDeleteMilestone, useMilestonesQuery, useUpdateMilestone } from '@/lib/api/milestones';
import { useProjectQuery, useProjectsPageQuery } from '@/lib/api/projects';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';

const LIMIT = 20;

export default function MilestonesPage() {
  const { hasPermission } = useHasPermission();
  const [projectId, setProjectId] = useState('');
  const [projectSearch, setProjectSearch] = useState('');
  const [page, setPage] = useState(1);
  const [name, setName] = useState('');
  const [dueDate, setDueDate] = useState('');
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
      setName(''); setDueDate(''); setError('');
    } catch (reason) { setError(getErrorMessage(reason, 'Could not create milestone.')); }
  }

  async function runAction(action: () => Promise<unknown>, fallback: string) {
    try { await action(); setError(''); }
    catch (reason) { setError(getErrorMessage(reason, fallback)); }
  }

  return <div className="space-y-6 pb-12">
    <header><h1 className="flex items-center gap-2 text-2xl font-bold"><Flag className="text-indigo-600" />Milestones</h1><p className="mt-1 text-sm text-slate-500">Track delivery dates and project outcomes.</p></header>
    <div className="grid gap-3 rounded-xl border bg-white p-4 sm:grid-cols-2"><input aria-label="Search projects" className="h-10 rounded-lg border px-3" placeholder="Search projects…" value={projectSearch} onChange={(event) => setProjectSearch(event.target.value)} /><select aria-label="Filter milestones by project" className="h-10 rounded-lg border px-3" value={projectId} onChange={(event) => { setProjectId(event.target.value); setPage(1); }}><option value="">All projects</option>{selectedProjectIsHidden && <option value={selectedProject.data!.id}>{selectedProject.data!.name}</option>}{projectOptions.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></div>
    {projects.isError && <ModuleError message="Projects could not be loaded." retry={() => projects.refetch()} />}
    {hasPermission(PERMISSIONS.PROJECTS.CREATE) && <form onSubmit={submit} className="grid gap-3 rounded-xl border bg-white p-4 sm:grid-cols-[1fr_1fr_auto_auto]"><select required className="h-10 rounded-lg border px-3" value={projectId} onChange={(event) => { setProjectId(event.target.value); setPage(1); }}><option value="">Select project</option>{selectedProjectIsHidden && <option value={selectedProject.data!.id}>{selectedProject.data!.name}</option>}{projectOptions.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select><input aria-label="Milestone name" className="h-10 rounded-lg border px-3" placeholder="Milestone name" value={name} onChange={(event) => setName(event.target.value)} /><input aria-label="Due date" className="h-10 rounded-lg border px-3" type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} /><button disabled={create.isPending} className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 text-white disabled:opacity-50"><Plus size={16} />{create.isPending ? 'Adding…' : 'Add'}</button></form>}
    {error && <ModuleError message={error}/>} {milestones.isError && <ModuleError message="Milestones could not be loaded." retry={() => milestones.refetch()} />}
    <div className="overflow-x-auto rounded-xl border bg-white"><table className="min-w-full text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="p-4">Milestone</th><th className="p-4">Project</th><th className="p-4">Due</th><th className="p-4">Status</th><th className="p-4">Actions</th></tr></thead><tbody>{milestones.data?.items.map((milestone) => <tr className="border-t" key={milestone.id}><td className="p-4 font-semibold">{milestone.name}</td><td className="p-4">{projects.data?.items.find((project) => project.id === milestone.project_id)?.name ?? milestone.project_id}</td><td className="p-4">{milestone.due_date?.slice(0,10) ?? '—'}</td><td className="p-4">{milestone.status}</td><td className="p-4"><div className="flex gap-3">{hasPermission(PERMISSIONS.PROJECTS.UPDATE) && milestone.status === 'Pending' && <button disabled={update.isPending} className="text-indigo-600 disabled:opacity-50" onClick={() => runAction(() => update.mutateAsync({ id: milestone.id, payload: { status: 'Completed' } }), 'Could not complete milestone.')}>Complete</button>}{hasPermission(PERMISSIONS.PROJECTS.DELETE) && <button disabled={remove.isPending} aria-label={`Delete ${milestone.name}`} className="text-rose-600 disabled:opacity-50" onClick={() => runAction(() => remove.mutateAsync(milestone.id), 'Could not delete milestone.')}><Trash2 size={16}/></button>}</div></td></tr>)}</tbody></table>{milestones.isLoading && <p className="p-8 text-center text-slate-500">Loading milestones…</p>}{!milestones.isLoading && !milestones.isError && !milestones.data?.items.length && <p className="p-8 text-center text-slate-500">No milestones found.</p>}<PageNavigator page={page} total={milestones.data?.total ?? 0} limit={LIMIT} onChange={setPage}/></div>
  </div>;
}
