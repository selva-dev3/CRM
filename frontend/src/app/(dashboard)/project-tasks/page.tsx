'use client';

import { useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { CheckSquare, GitBranch, Plus, Trash2 } from 'lucide-react';

import { ModalShell } from '@/components/common/modal-shell';
import { ModuleError, PageNavigator } from '@/components/common/module-page-state';
import { useHasPermission } from '@/hooks/use-has-permission';
import { useProjectQuery, useProjectsPageQuery } from '@/lib/api/projects';
import { TaskItem, useAddTaskDependencyMutation, useCompleteTaskMutation, useCreateTaskMutation, useDeleteTaskMutation, useRemoveTaskDependencyMutation, useTaskDependenciesQuery, useTasksPageQuery } from '@/lib/api/tasks';
import { PERMISSIONS } from '@/lib/permissions';
import { getErrorMessage } from '@/lib/utils';

const LIMIT = 20;

export default function ProjectTasksPage() {
  const searchParams = useSearchParams();
  const { hasPermission } = useHasPermission();
  const [projectId, setProjectId] = useState(() => searchParams.get('project_id') ?? '');
  const [projectSearch, setProjectSearch] = useState('');
  const [page, setPage] = useState(1);
  const [title, setTitle] = useState('');
  const [error, setError] = useState('');
  const [dependencyTask, setDependencyTask] = useState<TaskItem | null>(null);
  const [dependsOnTaskId, setDependsOnTaskId] = useState('');
  const projects = useProjectsPageQuery({ page: 1, limit: 50, search: projectSearch || undefined });
  const selectedProject = useProjectQuery(projectId);
  const projectOptions = projects.data?.items ?? [];
  const selectedProjectIsHidden = Boolean(
    selectedProject.data && !projectOptions.some((project) => project.id === projectId),
  );
  const tasks = useTasksPageQuery({ page, limit: LIMIT, project_id: projectId || undefined, project_linked: true });
  const createTask = useCreateTaskMutation();
  const completeTask = useCompleteTaskMutation();
  const deleteTask = useDeleteTaskMutation();
  const dependencies = useTaskDependenciesQuery(dependencyTask?.id ?? '');
  const addDependency = useAddTaskDependencyMutation();
  const removeDependency = useRemoveTaskDependencyMutation();

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!projectId || !title.trim()) return setError('Select a project and enter a task title.');
    try {
      await createTask.mutateAsync({ project_id: projectId, title: title.trim(), status: 'Pending', priority: 'Medium' });
      setTitle(''); setError('');
    } catch (reason) { setError(getErrorMessage(reason, 'Could not create project task.')); }
  }

  async function runAction(action: () => Promise<unknown>, fallback: string) {
    try { await action(); setError(''); }
    catch (reason) { setError(getErrorMessage(reason, fallback)); }
  }

  async function saveDependency() {
    if (!dependencyTask || !dependsOnTaskId) return;
    await runAction(
      () => addDependency.mutateAsync({ taskId: dependencyTask.id, dependsOnTaskId }),
      'Could not add task dependency.',
    );
    setDependsOnTaskId('');
  }

  return <div className="space-y-6 pb-12">
    <header><h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900"><CheckSquare className="text-indigo-600" />Project Tasks</h1><p className="mt-1 text-sm text-slate-500">Plan and track work using the existing CRM task workflow.</p></header>
    <div className="grid gap-3 rounded-xl border bg-white p-4 shadow-sm sm:grid-cols-2">
      <input aria-label="Search projects" className="h-10 rounded-lg border px-3" placeholder="Search projects…" value={projectSearch} onChange={(event) => setProjectSearch(event.target.value)} />
      <select aria-label="Filter tasks by project" className="h-10 rounded-lg border px-3" value={projectId} onChange={(event) => { setProjectId(event.target.value); setPage(1); }}><option value="">All projects</option>{selectedProjectIsHidden && <option value={selectedProject.data!.id}>{selectedProject.data!.name}</option>}{projectOptions.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select>
    </div>
    {projects.isError && <ModuleError message="Projects could not be loaded." retry={() => projects.refetch()} />}
    {hasPermission(PERMISSIONS.TASKS.CREATE) && <form onSubmit={submit} className="flex flex-col gap-3 rounded-xl border bg-white p-4 shadow-sm sm:flex-row"><select aria-label="Project for new task" required className="h-10 rounded-lg border px-3" value={projectId} onChange={(event) => { setProjectId(event.target.value); setPage(1); }}><option value="">Select project</option>{selectedProjectIsHidden && <option value={selectedProject.data!.id}>{selectedProject.data!.name}</option>}{projectOptions.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select><input aria-label="Task title" className="h-10 flex-1 rounded-lg border px-3" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="New project task" /><button disabled={createTask.isPending} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 font-semibold text-white disabled:opacity-50"><Plus size={16} />{createTask.isPending ? 'Adding…' : 'Add task'}</button></form>}
    {error && <ModuleError message={error} />}
    {tasks.isError && <ModuleError message="Project tasks could not be loaded." retry={() => tasks.refetch()} />}
    <div className="overflow-x-auto rounded-xl border bg-white shadow-sm"><table className="min-w-full text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="p-4">Task</th><th className="p-4">Project</th><th className="p-4">Status</th><th className="p-4">Due</th><th className="p-4">Actions</th></tr></thead><tbody>{tasks.data?.items.map((task) => <tr key={task.id} className="border-t"><td className="p-4 font-semibold">{task.title}</td><td className="p-4">{projects.data?.items.find((project) => project.id === task.project_id)?.name ?? task.project_id}</td><td className="p-4">{task.status}</td><td className="p-4">{task.due_date?.slice(0, 10) ?? '—'}</td><td className="p-4"><div className="flex flex-wrap gap-3">{hasPermission(PERMISSIONS.TASKS.UPDATE) && task.project_id && <button className="inline-flex items-center gap-1 text-slate-700 hover:text-indigo-700" onClick={() => { setDependencyTask(task); setDependsOnTaskId(''); }}><GitBranch size={15} />Dependencies</button>}{hasPermission(PERMISSIONS.TASKS.COMPLETE) && task.status !== 'Completed' && <button disabled={completeTask.isPending} className="text-indigo-600 disabled:opacity-50" onClick={() => runAction(() => completeTask.mutateAsync(task.id), 'Could not complete task.')}>Complete</button>}{hasPermission(PERMISSIONS.TASKS.DELETE) && <button disabled={deleteTask.isPending} aria-label={`Delete ${task.title}`} className="text-rose-600 disabled:opacity-50" onClick={() => runAction(() => deleteTask.mutateAsync(task.id), 'Could not delete task.')}><Trash2 size={16} /></button>}</div></td></tr>)}</tbody></table>{tasks.isLoading && <p className="p-8 text-center text-slate-500">Loading project tasks…</p>}{!tasks.isLoading && !tasks.isError && !tasks.data?.items.length && <p className="p-8 text-center text-slate-500">No project tasks found.</p>}<PageNavigator page={page} total={tasks.data?.total ?? 0} limit={LIMIT} onChange={setPage} /></div>
    <ModalShell isOpen={Boolean(dependencyTask)} onClose={() => setDependencyTask(null)} title={`Dependencies — ${dependencyTask?.title ?? ''}`} footer={<><button className="rounded-lg border px-4 py-2 text-sm font-semibold" onClick={() => setDependencyTask(null)}>Close</button><button className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={!dependsOnTaskId || addDependency.isPending} onClick={saveDependency}>Add dependency</button></>}>
      <div className="space-y-4 py-4">
        <div><label htmlFor="dependency-task" className="mb-1 block text-sm font-medium">This task depends on</label><select id="dependency-task" className="h-10 w-full rounded-lg border px-3" value={dependsOnTaskId} onChange={(event) => setDependsOnTaskId(event.target.value)}><option value="">Select another task</option>{tasks.data?.items.filter((task) => task.id !== dependencyTask?.id && task.project_id === dependencyTask?.project_id && !dependencies.data?.some((dependency) => dependency.depends_on_task_id === task.id)).map((task) => <option key={task.id} value={task.id}>{task.title}</option>)}</select></div>
        {dependencies.isLoading ? <p className="text-sm text-slate-500">Loading dependencies…</p> : dependencies.isError ? <ModuleError message="Task dependencies could not be loaded." retry={() => dependencies.refetch()} /> : dependencies.data?.length ? <ul className="divide-y rounded-lg border">{dependencies.data.map((dependency) => { const related = tasks.data?.items.find((task) => task.id === dependency.depends_on_task_id); return <li key={dependency.depends_on_task_id} className="flex items-center justify-between gap-3 p-3"><span className="text-sm">{related?.title ?? dependency.depends_on_task_id}</span><button aria-label={`Remove dependency ${related?.title ?? dependency.depends_on_task_id}`} className="text-rose-600 disabled:opacity-50" disabled={removeDependency.isPending} onClick={() => dependencyTask && runAction(() => removeDependency.mutateAsync({ taskId: dependencyTask.id, dependsOnTaskId: dependency.depends_on_task_id }), 'Could not remove task dependency.')}><Trash2 size={15} /></button></li>; })}</ul> : <p className="rounded-lg border border-dashed p-4 text-sm text-slate-500">No dependencies. This task can start immediately.</p>}
      </div>
    </ModalShell>
  </div>;
}
